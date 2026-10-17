"""Unified test reporting (TestReportService + repository + serializer + export in one small module).

Every test execution — voice deepfake check, speaker enrollment/verification, face verification, any multi-agent
investigation, connectivity checks, the automated test suite, frontend smoke tests — gets ONE persistent report:

  1. created with status RUNNING as soon as the test starts,
  2. updated after every step (inputs, steps, sanitized provider output, errors),
  3. finished with PASS / FAIL / HOLD / ERROR / SKIPPED — a failure is recorded, never dropped.

Two different things are kept apart:
  * execution_status — did the test run to completion? (completed / error / incomplete)
  * status           — were the test's acceptance criteria met?
A speaker check that correctly rejects a different speaker is a COMPLETED execution whose verification outcome is
NO_MATCH; HTTP 200 on its own never makes a test PASS.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Optional

from .db import SessionLocal, TestReport
from .schemas import new_id

APP_VERSION = "2.0.0"
ENVIRONMENT = os.getenv("GHOSTKEY_ENV", "local")
STATUSES = ("PASS", "FAIL", "HOLD", "ERROR", "SKIPPED")

# ---------- serializer / sanitizer ----------
_SECRET_KEY = re.compile(r"(api[_-]?key|token|authorization|secret|password|bearer|cookie)", re.I)
_BEARER = re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]+", re.I)
_BIOMETRIC_KEYS = {"embedding", "face_embedding", "reference_embedding"}


def _secrets() -> list[str]:
    vals = [os.getenv(k, "") for k in ("DETECTIF_API_KEY", "DETECTIFAI_API_KEY", "GHOSTKEY_API_TOKEN")]
    return [v for v in vals if v and len(v) >= 8]


def sanitize(obj: Any, _depth: int = 0) -> Any:
    """Remove secrets, raw binary and biometric vectors; keep everything else as-is."""
    if _depth > 25:
        return "[depth limit]"
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            ks = str(k)
            if _SECRET_KEY.search(ks) and not ks.endswith(("_configured", "_env_vars")):
                out[ks] = "[redacted]"
            elif ks in _BIOMETRIC_KEYS:
                out[ks] = "[biometric vector omitted]"
            else:
                out[ks] = sanitize(v, _depth + 1)
        return out
    if isinstance(obj, (list, tuple)):
        if len(obj) > 32 and all(isinstance(x, (int, float)) for x in obj):
            return f"[numeric vector of {len(obj)} values omitted]"
        return [sanitize(x, _depth + 1) for x in obj]
    if isinstance(obj, (bytes, bytearray)):
        return f"[{len(obj)} bytes omitted]"
    if isinstance(obj, str):
        s = _BEARER.sub(r"\1[redacted]", obj)
        for sec in _secrets():
            s = s.replace(sec, "[redacted]")
        return s
    if isinstance(obj, (int, float, bool)) or obj is None:
        return obj
    try:
        return sanitize(json.loads(json.dumps(obj, default=str)), _depth + 1)
    except Exception:
        return str(obj)


def iso(ts: Optional[float]) -> Optional[str]:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z") if ts else None


def audio_input(filename: str, content_type: Optional[str], data: bytes, meta: Optional[dict] = None, *, truth: str = "unknown",
                consent: Optional[bool] = None) -> dict:
    """Metadata for an audio input. The SHA-256 identifies the exact file submitted without storing the audio."""
    meta = meta or {}
    return {"kind": "audio", "file_name": filename, "content_type": content_type, "size_bytes": len(data),
            "duration_seconds": meta.get("duration_seconds"), "speech_seconds_estimate": meta.get("speech_seconds"),
            "sha256": hashlib.sha256(data).hexdigest(), "input_truth": truth, "consent": consent}


# ---------- service ----------
class ReportRun:
    """One test execution. Persisted on creation and after every update."""

    def __init__(self, category: str, name: str, *, feature: Optional[str] = None, endpoint: Optional[str] = None, scenario: Optional[str] = None,
                 expected: Optional[dict] = None, case_id: Optional[str] = None, correlation_id: Optional[str] = None,
                 speaker_id: Optional[str] = None, provider: Optional[str] = None, inputs: Optional[list] = None):
        self.id = new_id("rep")
        self.t0 = time.time()
        self.finished = False
        self.data: dict = {
            "report_id": self.id,
            "schema_version": 1,
            "test": {"name": name, "category": category, "feature": feature or category, "scenario": scenario,
                     "environment": ENVIRONMENT, "app_version": APP_VERSION, "git_commit": os.getenv("GHOSTKEY_GIT_COMMIT") or None,
                     "host_platform": platform.system()},
            "timestamps": {"started_at_utc": iso(self.t0), "finished_at_utc": None, "duration_ms": None},
            "ids": {"case_id": case_id, "correlation_id": correlation_id, "attempt_id": None, "speaker_id": speaker_id},
            "status": "RUNNING",
            "execution_status": "running",
            "verification_outcome": None,
            "inputs": list(inputs or []),
            "expected": expected,
            "actual": None,
            "execution": {"endpoint": endpoint, "provider": provider, "steps": [], "agents": [], "request_ids": []},
            "evidence": {},
            "diagnostics": {"failure_stage": None, "root_cause": None, "hypotheses": [], "errors": [], "technical": None,
                            "recommended_next_step": None, "retry_eligible": None},
            "assessment": {"summary": None, "reason": None, "acceptance_criteria": [], "status_basis": None},
        }
        self._save()

    # -- updates --
    def set_ids(self, **ids):
        self.data["ids"].update({k: v for k, v in ids.items() if v is not None})
        self._save()

    def add_input(self, item: dict):
        self.data["inputs"].append(item)
        self._save()

    def set_expected(self, expected: Optional[dict]):
        self.data["expected"] = expected
        self._save()

    def step(self, name: str, status: str = "completed", detail: str = "", *, started: Optional[float] = None, **data):
        now = time.time()
        self.data["execution"]["steps"].append({
            "name": name, "status": status, "detail": detail, "at_utc": iso(now),
            "t_ms": round((now - self.t0) * 1000), "duration_ms": round((now - started) * 1000) if started else None, "data": sanitize(data) if data else None,
        })
        rid = (data or {}).get("request_id")
        if rid and rid not in self.data["execution"]["request_ids"]:
            self.data["execution"]["request_ids"].append(rid)
        self._save()

    def evidence(self, **kw):
        self.data["evidence"].update(sanitize(kw))
        self._save()

    def execution(self, **kw):
        self.data["execution"].update(sanitize(kw))
        self._save()

    def finish(self, status: str, *, summary: str, reason: str = "", verification_outcome: Optional[str] = None, actual: Any = None,
               acceptance: Optional[list] = None, status_basis: str = "acceptance_criteria", execution_status: str = "completed",
               next_step: Optional[str] = None, retry_eligible: Optional[bool] = None, failure_stage: Optional[str] = None,
               root_cause: Optional[str] = None, hypotheses: Optional[list] = None):
        assert status in STATUSES, status
        now = time.time()
        d = self.data
        d["status"], d["execution_status"], d["verification_outcome"] = status, execution_status, verification_outcome
        d["actual"] = sanitize(actual)
        d["timestamps"].update(finished_at_utc=iso(now), duration_ms=round((now - self.t0) * 1000))
        d["assessment"].update(summary=summary, reason=reason or summary, acceptance_criteria=acceptance or [], status_basis=status_basis)
        dg = d["diagnostics"]
        dg["recommended_next_step"] = next_step or dg["recommended_next_step"]
        dg["retry_eligible"] = retry_eligible if retry_eligible is not None else dg["retry_eligible"]
        dg["failure_stage"] = failure_stage or dg["failure_stage"]
        dg["root_cause"] = root_cause or dg["root_cause"]
        if hypotheses:
            dg["hypotheses"] = hypotheses
        self.finished = True
        self._save(final=True)
        return self

    def error(self, exc: BaseException | str, stage: str, *, summary: Optional[str] = None, retry_eligible: bool = True, next_step: Optional[str] = None):
        msg = exc if isinstance(exc, str) else f"{type(exc).__name__}: {getattr(exc, 'message', None) or exc}"
        self.data["diagnostics"]["errors"].append({"stage": stage, "message": sanitize(str(msg))})
        if not isinstance(exc, str):
            self.data["diagnostics"]["technical"] = sanitize("".join(traceback.format_exception(exc))[-4000:])
        self.step(stage, "failed", sanitize(str(msg)))
        return self.finish("ERROR", summary=summary or f"Could not complete: {msg}", execution_status="error", failure_stage=stage,
                           retry_eligible=retry_eligible, next_step=next_step or "Check the diagnostics, fix the cause and retry.")

    # context manager: an unexpected exception still leaves an ERROR report behind
    def __enter__(self):
        return self

    def __exit__(self, et, ev, tb):
        if ev is not None and not self.finished:
            steps = self.data["execution"]["steps"]
            self.error(ev, steps[-1]["name"] + " → next step" if steps else "start")
        return False

    # -- repository --
    def _save(self, final: bool = False):
        d, ids = self.data, self.data["ids"]
        payload = json.dumps(sanitize(d), default=str)
        with SessionLocal() as db:
            row = db.get(TestReport, self.id) or TestReport(id=self.id, created_at=self.t0)
            row.category, row.name, row.feature = d["test"]["category"], d["test"]["name"], d["test"]["feature"]
            row.status, row.execution_status, row.verification_outcome = d["status"], d["execution_status"], d["verification_outcome"]
            row.case_id, row.correlation_id, row.speaker_id = ids.get("case_id"), ids.get("correlation_id"), ids.get("speaker_id")
            row.provider = d["execution"].get("provider")
            if final:
                row.finished_at, row.duration_ms = time.time(), d["timestamps"]["duration_ms"]
            row.payload = payload
            db.merge(row)
            db.commit()


def start(category: str, name: str, **kw) -> ReportRun:
    return ReportRun(category, name, **kw)


# ---------- queries / export ----------
def get(report_id: str) -> Optional[dict]:
    with SessionLocal() as db:
        row = db.get(TestReport, report_id)
        return json.loads(row.payload) if row else None


def query(*, status: str = "", category: str = "", q: str = "", provider: str = "", since: float = 0, until: float = 0,
          sort: str = "-created_at", limit: int = 100, offset: int = 0) -> dict:
    with SessionLocal() as db:
        base = db.query(TestReport)
        if status:
            base = base.filter(TestReport.status.in_(status.upper().split(",")))
        if category:
            base = base.filter(TestReport.category.in_(category.split(",")))
        if provider:
            base = base.filter(TestReport.provider == provider)
        if since:
            base = base.filter(TestReport.created_at >= since)
        if until:
            base = base.filter(TestReport.created_at <= until)
        if q:
            like = f"%{q}%"
            base = base.filter(TestReport.id.like(like) | TestReport.case_id.like(like) | TestReport.speaker_id.like(like) | TestReport.name.like(like))
        col = {"created_at": TestReport.created_at, "status": TestReport.status, "category": TestReport.category,
               "duration_ms": TestReport.duration_ms, "name": TestReport.name}.get(sort.lstrip("-"), TestReport.created_at)
        total = base.count()
        rows = base.order_by(col.desc() if sort.startswith("-") else col.asc()).offset(offset).limit(min(limit, 500)).all()
        return {"total": total, "items": [_summary(r) for r in rows]}


def _summary(r: TestReport) -> dict:
    p = json.loads(r.payload)
    return {"report_id": r.id, "name": r.name, "category": r.category, "feature": r.feature, "status": r.status,
            "execution_status": r.execution_status, "verification_outcome": r.verification_outcome, "case_id": r.case_id,
            "speaker_id": r.speaker_id, "provider": r.provider, "created_at": r.created_at, "created_at_utc": iso(r.created_at),
            "duration_ms": r.duration_ms, "summary": p.get("assessment", {}).get("summary")}


def stats() -> dict:
    with SessionLocal() as db:
        rows = db.query(TestReport.status, TestReport.category).all()
    by_status = {s: 0 for s in (*STATUSES, "RUNNING")}
    by_category: dict = {}
    for s, c in rows:
        by_status[s] = by_status.get(s, 0) + 1
        by_category[c] = by_category.get(c, 0) + 1
    return {"total": len(rows), "by_status": by_status, "by_category": by_category, "recent": query(limit=8)["items"]}


def mark_interrupted(older_than_seconds: float = 600) -> int:
    """On startup: reports still RUNNING from a previous process never finished — mark them, don't lose them."""
    cutoff, n = time.time() - older_than_seconds, 0
    with SessionLocal() as db:
        for row in db.query(TestReport).filter(TestReport.status == "RUNNING", TestReport.created_at < cutoff).all():
            p = json.loads(row.payload)
            p["status"], p["execution_status"] = "ERROR", "incomplete"
            p["diagnostics"]["failure_stage"] = (p["execution"]["steps"][-1]["name"] if p["execution"]["steps"] else "start")
            p["diagnostics"]["errors"].append({"stage": "interrupted", "message": "The application stopped before this test finished."})
            p["assessment"]["summary"] = "Incomplete: the test was interrupted (application restart or crash)."
            row.status, row.execution_status, row.payload = "ERROR", "incomplete", json.dumps(p)
            n += 1
        db.commit()
    return n


# ---------- status helpers ----------
OUTCOME_STATUS = {"VERIFIED_AND_AUTHORIZED": "PASS", "DENIED": "FAIL", "HOLD_FOR_VERIFICATION": "HOLD", "ESCALATED_FOR_REVIEW": "HOLD"}


def finish_investigation(run: ReportRun, rec: dict, expected: Optional[dict] = None) -> None:
    """Fill a report from a finished multi-agent investigation record and close it."""
    req, dec = rec["request"], rec["decision"]
    run.set_ids(case_id=rec["case_id"], correlation_id=rec["correlation_id"])
    if not run.data["inputs"]:
        run.data["inputs"].append({"kind": "case data", "use_case": rec["use_case"], "scenario": rec.get("scenario_id"), "claimed_identity": req.get("claimed_identity"),
                                   "requested_action": (req.get("requested_action") or {}).get("type"), "input_truth": "simulated fixtures" if rec.get("simulated_inputs") else "live / structured",
                                   "simulated": bool(rec.get("simulated_inputs"))})
    agents = []
    for f in rec["findings"]:
        agents.append({"agent": f["agent"], "version": f.get("agent_version"), "finding": f["finding_type"], "status": f["status"],
                       "execution_status": f.get("execution_status", "completed"), "disposition": f.get("disposition"),
                       "evidence_source": f.get("evidence_source"), "summary": (f.get("observations") or [""])[0], "errors": f.get("errors")})
    run.execution(agents=agents, agent_order=[f["agent"] for f in rec["findings"]] + ["adversarial_critic", "evidence_reconciler", "policy_engine"])
    for t in rec["timeline"]:
        if t["step"] in ("provider", "face_model", "critic", "challenge", "response", "reconcile", "policy"):
            run.data["execution"]["steps"].append({"name": f"{t['step']} · {t['actor']}", "status": "completed", "detail": t["detail"],
                                                   "at_utc": iso(rec["created_at"] + t["t"]), "t_ms": None, "duration_ms": None, "data": None})
    providers = []
    for key in ("audio_authenticity", "speaker_verification"):
        p = req.get(key)
        if p:
            providers.append({"capability": p["capability"], "status": p["status"], "simulated": p["simulated"], "classification": p.get("classification"),
                              "score": p.get("score"), "threshold": p.get("threshold"), "score_semantics": p.get("score_semantics"),
                              "operation_id": p.get("raw_result_reference"), "request_id": (p.get("details") or {}).get("request_id"),
                              "model": (p.get("details") or {}).get("model"), "speaker_id": (p.get("details") or {}).get("speaker_id"), "error": p.get("error")})
            rid = (p.get("details") or {}).get("request_id")
            if rid:
                run.data["execution"]["request_ids"].append(rid)
    unmet = [r for r in dec["requirements"] if not r["satisfied"] and "informational" not in r["name"]]
    run.evidence(provider_results=providers,
                 face={"frames": len(req.get("face_frames") or []), "similarities": [fr.get("best_similarity") for fr in req.get("face_frames") or []],
                       "model": req.get("face_model")} if req.get("face_frames") else None,
                 contextual=[a for a in agents if a["finding"] in ("action_risk", "number_lifecycle", "claim_consistency")],
                 critic=[{"round": c.get("round"), "target": c.get("target_agent"), "question": c.get("question"), "outcome": c.get("outcome"),
                          "response": c.get("response")} for c in rec["challenges"]],
                 reconciliation={"claims": len(rec["reconciliation"].get("claims", [])), "changed_after_challenge": rec["reconciliation"].get("changed_after_challenge"),
                                 "unresolved": rec["reconciliation"].get("unresolved")},
                 policy={"outcome": dec["outcome"], "headline": dec.get("headline"), "reasons": dec["reasons"], "rules_fired": dec["rules_fired"],
                         "requirements": dec["requirements"]},
                 missing_evidence=[f"{r['name']}: {r['detail']}" for r in unmet],
                 uncertainty=sorted({lim for f in rec["findings"] for lim in (f.get("limitations") or [])})[:8],
                 simulated_inputs=rec.get("simulated_inputs"))
    outcome = dec["outcome"]
    failed_agents = [a["agent"] for a in agents if a["execution_status"] != "completed"]
    if expected and expected.get("outcome"):
        ok = outcome == expected["outcome"]
        status, basis = ("PASS" if ok else "FAIL"), "expected_vs_actual"
        acceptance = [{"criterion": f"final decision is {expected['outcome']}", "satisfied": ok, "actual": outcome}]
    elif expected and expected.get("findings"):
        st = {f["finding_type"]: f["status"] for f in rec["findings"]}
        acceptance = [{"criterion": f"{k} is {v}", "satisfied": st.get(k) == v, "actual": st.get(k)} for k, v in expected["findings"].items()]
        status, basis = ("PASS" if all(a["satisfied"] for a in acceptance) else "FAIL"), "expected_vs_actual"
    elif expected and expected.get("evidence"):
        acceptance = _evidence_criteria(expected["evidence"], rec)
        status, basis = ("PASS" if all(a["satisfied"] for a in acceptance) else "FAIL"), "expected_vs_actual"
    else:
        status, basis = OUTCOME_STATUS.get(outcome, "HOLD"), "policy_outcome"
        acceptance = [{"criterion": r["name"], "satisfied": r["satisfied"], "actual": r["detail"]} for r in dec["requirements"]]
    run.finish(status, summary=dec.get("headline") or dec["reasons"][-1], reason=dec["reasons"][-1], verification_outcome=outcome,
               actual={"outcome": outcome, "headline": dec.get("headline")}, acceptance=acceptance, status_basis=basis,
               next_step=next((f.get("recommended_next_step") for f in rec["findings"] if f.get("recommended_next_step")), None),
               hypotheses=[f"Agent {a} did not complete — its evidence is treated as missing." for a in failed_agents] or None)


def _evidence_criteria(exp: str, rec: dict) -> list[dict]:
    st = {f["finding_type"]: f["status"] for f in rec["findings"]}
    voice, speaker = st.get("voice_authenticity"), st.get("speaker_identity")
    if exp == "same_person":
        return [{"criterion": "speaker check confirms the enrolled person", "satisfied": speaker in ("SPEAKER_MATCH_SUPPORTED",), "actual": speaker},
                {"criterion": "no synthetic indicators", "satisfied": voice != "SYNTHETIC_INDICATORS", "actual": voice}]
    if exp == "different_person":
        return [{"criterion": "speaker check rejects the claimed identity", "satisfied": speaker == "SPEAKER_MISMATCH_SUSPECTED", "actual": speaker},
                {"criterion": "request is not authorized", "satisfied": rec["decision"]["outcome"] != "VERIFIED_AND_AUTHORIZED", "actual": rec["decision"]["outcome"]}]
    if exp == "ai_voice":
        return [{"criterion": "synthetic indicators detected", "satisfied": voice == "SYNTHETIC_INDICATORS", "actual": voice},
                {"criterion": "request is not authorized", "satisfied": rec["decision"]["outcome"] != "VERIFIED_AND_AUTHORIZED", "actual": rec["decision"]["outcome"]}]
    if exp == "real_human":
        return [{"criterion": "no synthetic indicators", "satisfied": voice == "NO_SYNTHETIC_INDICATORS", "actual": voice}]
    return [{"criterion": f"unknown expectation '{exp}'", "satisfied": False, "actual": None}]


SOFT_PROVIDER_ERRORS = {"insufficient_speech", "audio_too_short", "audio_too_long", "unsupported_format", "invalid_audio", "bad_duration",
                        "corrupt_audio", "empty_file", "no_speech"}


def provider_error_status(code: Optional[str], provider_status: Optional[str]) -> str:
    """Low-quality / invalid audio → HOLD (retry with better audio); infrastructure or auth problems → ERROR."""
    if code and any(code.startswith(c) or c in code for c in SOFT_PROVIDER_ERRORS):
        return "HOLD"
    return "ERROR"
