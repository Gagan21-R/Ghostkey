"""Investigation workflow (runs directly in FastAPI; n8n is optional and not required):
input validation → provider evidence → parallel specialists → shared evidence store → adversarial critic →
bounded challenge loop → evidence reconciliation → deterministic policy engine → audit log."""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor

from concurrent.futures import TimeoutError as FutureTimeout

from . import report_service as test_reports
from . import (adversarial_critic, audit_service, contextual_risk_agent, evidence_reconciler, exam_identity_agent, insurance_claim_agent, policy_engine,
               sim_risk_agent, speaker_identity_agent, voice_authenticity_agent)
from .schemas import Finding
from .db import DecisionRow, FaceResultRow, FindingRow, Investigation, ProviderResultRow, SessionLocal
from .schemas import FindingStatus as F
from .schemas import InvestigationRequest, new_id

MAX_ROUNDS = 2
SPECIALISTS = {
    "banking": [voice_authenticity_agent, speaker_identity_agent, contextual_risk_agent],
    "family": [voice_authenticity_agent, speaker_identity_agent, sim_risk_agent, contextual_risk_agent],
    "exam": [exam_identity_agent, contextual_risk_agent],
    "insurance": [voice_authenticity_agent, speaker_identity_agent, insurance_claim_agent, contextual_risk_agent],
}
AGENT_TIMEOUT = 10.0  # seconds per specialist
RESPONDERS = {m.NAME: m for m in (voice_authenticity_agent, speaker_identity_agent, exam_identity_agent, sim_risk_agent, contextual_risk_agent, insurance_claim_agent)}


def _source(f: Finding, req: InvestigationRequest) -> str:
    for ftype, p in (("voice_authenticity", req.audio_authenticity), ("speaker_identity", req.speaker_verification)):
        if f.finding_type == ftype and p:
            if p.simulated:
                return "simulated_fixture"
            # a check that never completed is not provider output
            return "live_provider" if p.status.value in ("COMPLETED", "INCONCLUSIVE") else "none"
    if f.finding_type == "exam_identity" and req.face_frames:
        return "simulated_fixture" if any(fr.simulated for fr in req.face_frames) else "local_face_model"
    if f.finding_type == "number_lifecycle":
        return "simulated_fixture" if req.carrier_events else "none"
    if f.finding_type in ("action_risk", "claim_consistency"):
        return "structured_case_data"
    return f.evidence_source


def _collect(module, fut, req):
    try:
        f = fut.result(timeout=AGENT_TIMEOUT)
    except FutureTimeout:
        f = Finding(agent=module.NAME, agent_version=module.VERSION, finding_type="timeout", status=F.UNAVAILABLE, execution_status="timeout",
                    errors=[f"agent exceeded {AGENT_TIMEOUT}s"], recommended_next_step="Treat as missing evidence.")
    except Exception as e:  # an agent crash is recorded, never silently turned into a pass
        f = Finding(agent=module.NAME, agent_version=module.VERSION, finding_type="error", status=F.UNAVAILABLE, execution_status="failed",
                    errors=[f"{type(e).__name__}: {e}"], recommended_next_step="Treat as missing evidence.")
    f.correlation_id = req.correlation_id
    f.evidence_source = _source(f, req)
    return f


CATEGORY = {"exam": "face_verification", "family": "family_sim_risk", "insurance": "insurance_claim", "banking": "banking_voice"}


def run(req: InvestigationRequest, report: "test_reports.ReportRun | None" = None, expected: dict | None = None) -> dict:
    """Run one investigation. Every run is covered by a persistent test report (created here unless the caller
    already started one, e.g. to record its provider calls); the record carries its `report_id`."""
    report = report or test_reports.start(CATEGORY.get(req.use_case, req.use_case), req.title or f"{req.use_case} investigation",
                                          feature=req.use_case, scenario=req.scenario_id, endpoint="orchestrator.run")
    report.set_ids(correlation_id=req.correlation_id)
    if expected and not report.data.get("expected"):
        report.set_expected(expected)
    try:
        record = _run(req)
    except Exception as e:
        report.error(e, "multi-agent investigation")
        raise
    record["report_id"] = report.id
    with SessionLocal() as db:  # keep the stored case linked to its report
        row = db.get(Investigation, record["investigation_id"])
        if row:
            row.record = json.dumps(record, default=str)
            db.commit()
    test_reports.finish_investigation(report, record, expected)
    return record


def _run(req: InvestigationRequest) -> dict:
    inv_id = new_id("inv")
    t0 = time.time()
    timeline: list[dict] = []

    def log(step: str, actor: str, detail: str, data: dict | None = None):
        timeline.append({"t": round(time.time() - t0, 3), "step": step, "actor": actor, "detail": detail, "data": data or {}})

    log("input", "orchestrator", f"Use case '{req.use_case}', action '{req.requested_action.type}', role '{req.actor_role}'.")
    provider_facts = []
    for p in (req.audio_authenticity, req.speaker_verification):
        if p:
            label = "SIMULATED fixture" if p.simulated else "live DetectifAI"
            log("provider", "detectify_provider", f"{p.capability}: {p.status.value} ({label})", p.model_dump())
            provider_facts.append({"source": f"detectify_ai/{p.capability}", "simulated": p.simulated, "status": p.status.value,
                                   "classification": p.classification, "score": p.score, "reference": p.raw_result_reference})
    if req.face_frames:
        sim = any(fr.simulated for fr in req.face_frames)
        log("face_model", "face_service", f"{len(req.face_frames)} frame(s) analysed — {'SIMULATED frame outputs' if sim else (req.face_model or {}).get('name', 'OpenCV YuNet + SFace')}",
            {"faces": [fr.faces for fr in req.face_frames], "similarity": [fr.best_similarity for fr in req.face_frames]})
    for e in req.carrier_events:
        log("carrier_event", "simulated_carrier", f"{e.get('type')} [SIMULATED]", e)
    if req.challenge_check:
        log("session", "session_service", f"challenge: {req.challenge_check.get('reason')}", req.challenge_check)
    if req.approval_check:
        log("session", "session_service", f"approval: {req.approval_check.get('reason')}", req.approval_check)

    agents = SPECIALISTS[req.use_case]
    with ThreadPoolExecutor(max_workers=len(agents)) as pool:  # specialists work independently, in parallel, each with a timeout
        futures = [(m, pool.submit(m.analyze, req)) for m in agents]
        findings = [_collect(m, fu, req) for m, fu in futures]
    if req.force_disagreement:  # scenario G: deliberately conflicting specialist outputs
        for f in findings:
            if f.finding_type == "speaker_identity":
                f.status, f.observations = F.SPEAKER_MATCH_SUPPORTED, f.observations + ["(Scenario G fixture: speaker agent reports a match.)"]
    original = [json.loads(f.model_dump_json()) for f in findings]
    for f in findings:
        log("finding", f.agent, f"{f.finding_type} → {f.status.value}", json.loads(f.model_dump_json()))

    challenges = []
    asked: set = set()
    for rnd in range(1, MAX_ROUNDS + 1):
        new = adversarial_critic.challenge(findings, rnd, asked)
        if not new:
            log("critic", "adversarial_critic", f"Round {rnd}: no further challenges — evidence sufficient for review.")
            break
        for ch in new:
            log("challenge", "adversarial_critic", f"Round {rnd} → {ch.target_agent}: {ch.question}", ch.model_dump())
            target = next(f for f in findings if f.finding_id == ch.target_finding_id)
            responder = RESPONDERS.get(ch.target_agent)
            ch = responder.respond(target, ch, req) if responder else ch
            if ch.outcome is None:
                ch.outcome = "unresolved"
            challenges.append(ch)
            log("response", ch.target_agent, f"{ch.outcome}: {ch.response}", {"finding_status": target.status.value, "revision": target.revision})
    else:
        log("critic", "adversarial_critic", f"Round limit ({MAX_ROUNDS}) reached.")

    issues = adversarial_critic.unresolved(findings, challenges)
    reconciliation = evidence_reconciler.reconcile(original, findings, challenges, issues, provider_facts)
    log("reconcile", "evidence_reconciler", f"{len(reconciliation['claims'])} claims, {len(reconciliation['changed_after_challenge'])} changed, {len(issues)} unresolved.", reconciliation)

    decision = policy_engine.decide(req, findings, issues)
    log("policy", "policy_engine", f"{decision.outcome.value}: {decision.reasons[-1]}", decision.model_dump())

    record = {
        "investigation_id": inv_id,
        "case_id": inv_id,
        "correlation_id": req.correlation_id,
        "use_case": req.use_case,
        "scenario_id": req.scenario_id,
        "title": req.title or f"{req.use_case} · {req.requested_action.type}",
        "request": json.loads(req.model_dump_json()),
        "findings": [json.loads(f.model_dump_json()) for f in findings],
        "original_findings": original,
        "challenges": [c.model_dump() for c in challenges],
        "reconciliation": reconciliation,
        "decision": json.loads(decision.model_dump_json()),
        "timeline": timeline,
        "simulated_inputs": any(p.simulated for p in (req.audio_authenticity, req.speaker_verification) if p) or bool(req.carrier_events) or any(fr.simulated for fr in req.face_frames),
        "created_at": t0,
    }
    _persist(record, req)
    audit_service.record("investigation.decided", inv_id, {"use_case": req.use_case, "scenario": req.scenario_id, "outcome": decision.outcome.value, "action": req.requested_action.type})
    return record


def _persist(record: dict, req: InvestigationRequest) -> None:
    inv_id = record["investigation_id"]
    with SessionLocal() as db:
        db.add(Investigation(id=inv_id, use_case=req.use_case, scenario_id=req.scenario_id, title=record["title"],
                             outcome=record["decision"]["outcome"], created_at=record["created_at"], record=json.dumps(record, default=str)))
        for p in (req.audio_authenticity, req.speaker_verification):
            if p:
                db.add(ProviderResultRow(investigation_id=inv_id, capability=p.capability, status=p.status.value, simulated=p.simulated, payload=json.loads(p.model_dump_json())))
        if req.face_frames:
            db.add(FaceResultRow(investigation_id=inv_id, payload=[json.loads(f.model_dump_json()) for f in req.face_frames]))
        for f in record["findings"]:
            db.add(FindingRow(id=f["finding_id"], investigation_id=inv_id, agent=f["agent"], status=f["status"], disposition=f["disposition"], payload=f))
        db.add(DecisionRow(investigation_id=inv_id, outcome=record["decision"]["outcome"], payload=record["decision"]))
        db.commit()
