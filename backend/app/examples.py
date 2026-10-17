"""Real-human example library (exam faces: Caltech Faces 1999; voices: MINDS-14 real callers + labelled AI voices).

Exam examples always run the real local face model. Voice examples call DetectifAI only when `live=True`
(1 credit-charged check); otherwise the voice check is reported as not run — never faked."""
from __future__ import annotations

import json
import os
from functools import lru_cache

from . import face_service, orchestrator, session_service
from . import report_service as test_reports
from .db import Identity, SessionLocal
from .detectify_provider import provider
from .file_validation import validate_audio
from .insurance_data import SYNTHETIC_NOTICE
from .schemas import FaceFrame, InvestigationRequest, ProviderResult, ProviderStatus, RequestedAction

EX_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")


@lru_cache(maxsize=8)
def manifest(use_case: str) -> dict:
    with open(os.path.join(EX_DIR, use_case, "manifest.json"), encoding="utf-8") as fh:
        return json.load(fh)


def listing(use_case: str) -> dict:
    m = manifest(use_case)
    items = m["cases"] if use_case == "exam" else m["examples"]
    media = lambda p: f"/api/media/{use_case}/{p}" if p else None  # noqa: E731
    out = []
    for e in items:
        e = dict(e)
        if use_case == "exam":
            e["reference_url"] = media(e["reference"])
            e["frame_urls"] = [media(f) for f in e["frames"]]
        else:
            e["audio_url"] = media(e["audio"])
        out.append(e)
    return {**{k: v for k, v in m.items() if k not in ("cases", "examples")}, "examples": out}


def _find(use_case: str, eid: str) -> dict:
    items = manifest(use_case)["cases" if use_case == "exam" else "examples"]
    for e in items:
        if e["id"] == eid:
            return e
    raise KeyError(eid)


def _not_run() -> ProviderResult:
    return ProviderResult(capability="audio_authenticity", status=ProviderStatus.UNAVAILABLE, error="not run: click 'Analyse with DetectifAI' to spend 1 check",
                          limitations=["Voice check not performed — this is missing evidence, not a pass."])


def _audio(use_case: str, e: dict, live: bool) -> ProviderResult:
    if not live:
        return _not_run()
    path = os.path.join(EX_DIR, use_case, e["audio"])
    with open(path, "rb") as fh:
        data = fh.read()
    ctype = "audio/mpeg" if path.endswith(".mp3") else "audio/wav"
    return provider.audio_authenticity(data, filename=os.path.basename(path), content_type=ctype)


def _auth(use_case: str, identity: str, action: dict) -> tuple[dict, dict]:
    device = "Registered phone (simulated)"
    s = session_service.create_session(use_case, identity, action)
    c = session_service.issue_challenge(s["session_id"])
    ch = session_service.verify_challenge(s["session_id"], c["challenge_id"], c["nonce_for_trusted_channel"])
    a = session_service.request_approval(s["session_id"], action, device)
    session_service.decide_approval(a["approval_id"], True, device)
    return ch, session_service.check_approval(a["approval_id"], action)


def run(use_case: str, eid: str, live: bool = False) -> dict:
    e = _find(use_case, eid)
    if use_case == "exam":
        req = _exam(e)
    elif use_case == "family":
        req = _family(e, live)
    elif use_case == "banking":
        req = _banking(e, live)
    else:
        req = _insurance(e, live)
    if use_case == "exam":
        expected = {"findings": {"exam_identity": e["expected_state"]}, "description": f"ground truth: {e['ground_truth']}"}
    elif live:
        expected = {"evidence": "ai_voice" if e.get("voice_truth") == "ai_synthetic" else "real_human", "description": f"labelled {e.get('voice_truth')}"}
    else:
        expected = None  # free run: the voice check is deliberately not performed, so only the policy outcome is reported
    rec = orchestrator.run(req, expected=expected)
    rec["example"] = {"id": eid, "use_case": use_case, "live_voice_check": live and use_case != "exam",
                      "ground_truth": e.get("ground_truth") or e.get("voice_truth"), "source": e.get("voice_source") or e.get("sources")}
    return rec


def _banking(e: dict, live: bool) -> InvestigationRequest:
    action = RequestedAction(type=e["action"], amount=e["amount"], details={"customer": e["customer"]})
    ch = ap = None
    if e["auth"] in ("full", "challenge_only", "replay"):
        s = session_service.create_session("banking", e["id"], action.model_dump())
        c = session_service.issue_challenge(s["session_id"])
        ch = session_service.verify_challenge(s["session_id"], c["challenge_id"], c["nonce_for_trusted_channel"])
        if e["auth"] == "replay":
            ch = session_service.verify_challenge(s["session_id"], c["challenge_id"], c["nonce_for_trusted_channel"])
        if e["auth"] == "full":
            a = session_service.request_approval(s["session_id"], action.model_dump(), "Registered phone (simulated)")
            session_service.decide_approval(a["approval_id"], True, "Registered phone (simulated)")
            ap = session_service.check_approval(a["approval_id"], action.model_dump())
    return InvestigationRequest(use_case="banking", scenario_id=e["id"], title=f"Banking example {e['id']}: {e['customer']} — {e['action']}",
                                claimed_identity=f"{e['customer']} (customer)", actor_role=e["role"], requested_action=action, transcript=e["transcript"],
                                audio_authenticity=_audio("banking", e, live), speaker_reference_enrolled=False, challenge_check=ch, approval_check=ap)


EXPECTATIONS = {"same_person": "the voice is the enrolled person (speaker match expected)",
                "different_person": "the voice is NOT the enrolled person (speaker mismatch expected)",
                "ai_voice": "the audio is AI-generated (synthetic indicators expected)", "real_human": "the audio is a real human voice"}


def run_custom(use_case: str, eid: str, data: bytes, filename: str, ctype: str, transcript: str = "", speaker_identity_id: str = "", person_identity_id: str = "",
               expected: str = "") -> dict:
    """Judge test: the judge's own recording or uploaded file (e.g. an AI clone) inside an example's context.
    Always a live DetectifAI call — 1 check, or 2 when verifying against an enrolled voiceprint."""
    if use_case == "exam":
        raise ValueError("exam tests use the webcam / image check")
    run = test_reports.start({"family": "family_sim_risk", "insurance": "insurance_claim", "banking": "banking_voice"}[use_case],
                             f"Judge test · {use_case} · context {eid}", feature=use_case, scenario=eid, endpoint=f"POST /api/test/{use_case}", provider="DetectifAI",
                             expected={"evidence": expected, "description": EXPECTATIONS.get(expected, expected)} if expected else None)
    try:
        meta = validate_audio(filename, ctype, data)
    except ValueError as err:
        run.add_input(test_reports.audio_input(filename, ctype, data))
        run.step("validate audio", "failed", str(err))
        run.finish("ERROR", summary=f"Audio rejected before analysis: {err}", execution_status="error", failure_stage="validate audio", retry_eligible=True,
                   next_step="Upload a supported audio file of 4–120 s.")
        err.report_id = run.id  # type: ignore[attr-defined]
        raise
    run.add_input(test_reports.audio_input(filename, ctype, data, meta, truth="judge-supplied (unknown)", consent=True))
    run.step("validate audio", "completed", f"{meta['duration_seconds']:.1f} s" if meta["duration_seconds"] else "format accepted; DetectifAI measures duration")
    e = _find(use_case, eid)
    req = {"family": _family, "insurance": _insurance, "banking": _banking}[use_case](e, False)
    spk = df = None
    who = person = None
    if person_identity_id:  # a person the judge added: they become the caller / customer / policyholder
        with SessionLocal() as db:
            ident = db.get(Identity, person_identity_id)
            if not ident:
                raise ValueError("unknown person")
            person = ident.name
        req.claimed_identity = person
        if req.policyholder:
            req.policyholder["name"] = person
        if req.claim:
            req.claim["claimant"] = person
    if speaker_identity_id:
        with SessionLocal() as db:
            ident = db.get(Identity, speaker_identity_id)
            if not ident or not ident.speaker_enrolled:
                raise ValueError("that identity has no enrolled voiceprint")
            who = ident.name
            speaker_id = ident.speaker_id
        run.set_ids(speaker_id=speaker_id)
        t = __import__("time").time()
        spk, df = provider.speaker_verification(data, speaker_id, filename=filename, content_type=ctype, detect_deepfake=True)
        run.step("DetectifAI POST /v1/speakers/verify", "completed" if spk.status.value == "COMPLETED" else "failed",
                 f"speaker_id={speaker_id}: {spk.classification or spk.error}", started=t, request_id=(spk.details or {}).get("request_id"))
    t = __import__("time").time()
    req.audio_authenticity = df or provider.audio_authenticity(data, filename=filename, content_type=ctype)
    if not df:
        a = req.audio_authenticity
        run.step("DetectifAI POST /v1/deepfake/detect", "completed" if a.status.value in ("COMPLETED", "INCONCLUSIVE") else "failed",
                 f"{a.classification or a.error}", started=t, request_id=(a.details or {}).get("request_id"))
    req.speaker_verification = spk
    req.speaker_reference_enrolled = bool(spk)
    if who and not person:
        req.claimed_identity = who
    if transcript.strip():
        req.transcript = transcript.strip()
    req.title = f"Judge test · {use_case} · context {eid}" + (f" · as {person}" if person else "") + (f" · voiceprint of {who}" if who else "")
    rec = orchestrator.run(req, report=run, expected=run.data["expected"])
    rec["example"] = {"id": eid, "use_case": use_case, "judge_test": True, "uploaded_file": filename, "live_voice_check": True,
                      "speaker_checked_against": who, "person": person, "upload": meta}
    return rec


def _exam(e: dict) -> InvestigationRequest:
    read = lambda p: open(os.path.join(EX_DIR, "exam", p), "rb").read()  # noqa: E731
    ref = face_service.embed(read(e["reference"])) if e.get("reference") else {"ok": False}
    frames = [FaceFrame(**face_service.analyze_frame(read(f), ref.get("embedding"), i)) for i, f in enumerate(e["frames"])]
    return InvestigationRequest(use_case="exam", scenario_id=e["id"], title=f"Exam example {e['id']}: {e['student']} — {e['scenario']}",
                                claimed_identity=f"{e['student']} (registered student)", actor_role="student", requested_action=RequestedAction(type="start_exam"),
                                face_frames=frames, face_reference_enrolled=bool(ref.get("ok")), face_model=face_service.MODEL_INFO)


def _family(e: dict, live: bool) -> InvestigationRequest:
    iv = {"method": "code on the protected person's enrolled recovery channel", "status": e["independent_verification"]} if e["independent_verification"] else None
    return InvestigationRequest(use_case="family", scenario_id=e["id"], title=f"Family example {e['id']}: {e['claimed_caller']} — {e['action']}",
                                identity_id="id-asha", claimed_identity=e["claimed_caller"], actor_role="family_member",
                                requested_action=RequestedAction(type=e["action"], amount=e["amount"], details={"relation": e["relation"]}),
                                transcript=e["transcript"], audio_authenticity=_audio("family", e, live), speaker_reference_enrolled=False,
                                carrier_events=[{**c, "simulated": True} for c in e["carrier_events"]], account_events=e["account_events"],
                                independent_verification=iv)


def _insurance(e: dict, live: bool) -> InvestigationRequest:
    claim = {"claim_id": e["claim_id"], "policyholder_id": e["id"], "claimant": e["policyholder"], "claimant_relation": "self", "claim_type": e["claim_type"],
             "amount": e["amount"] or 0, "incident_date": "2026-10-08", "reported_date": "2026-10-10", "status": "Submitted", "documents": e["documents"],
             "required_documents": e["required_documents"], "requested_action": e["action"],
             "new_payout_account": "New bank ••7765" if e["anomaly"] == "payout_changed" or e["action"] == "change_payout_details" else None,
             "duplicate_of": "CLM-2025-0877" if e["anomaly"] == "duplicate" else None, "synthetic": True}
    ph = {"id": e["id"], "name": e["policyholder"], "policy_ref": e["policy_ref"], "sum_insured": 2000000, "policy_start": "2023-04-01",
          "payout_account_changed_at": "2026-10-09" if e["anomaly"] == "payout_changed" else None, "authorized_representatives": [], "voice_enrolled": False,
          "synthetic": True, "notice": SYNTHETIC_NOTICE}
    action = RequestedAction(type=e["action"], amount=e["amount"], details={"claim_id": e["claim_id"]})
    ch = ap = None
    if e["auth"] == "full":
        ch, ap = _auth("insurance", e["id"], action.model_dump())
    return InvestigationRequest(use_case="insurance", scenario_id=e["id"], title=f"Insurance example {e['id']}: {e['policyholder']} — {e['action']}",
                                identity_id=e["id"], claimed_identity=e["policyholder"], actor_role="policyholder", requested_action=action,
                                transcript=e["transcript"], audio_authenticity=_audio("insurance", e, live), claim=claim, policyholder=ph,
                                challenge_check=ch, approval_check=ap)
