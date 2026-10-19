"""GHOSTKEY 2.0 API. All /api routes except /api/health need the internal token (X-GhostKey-Token),
which only the Next.js server holds — the browser never sees it or the DetectifAI key."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile  # noqa: E402

import time  # noqa: E402

from fastapi.responses import FileResponse, JSONResponse  # noqa: E402

from . import report_service as test_reports  # noqa: E402
from . import audit_service, examples, face_service, orchestrator, scenarios, session_service, speaker_identity_agent, voice_authenticity_agent  # noqa: E402
from .file_validation import AUDIO_EXT, MAX_AUDIO_MB, MAX_IMAGE_MB, UploadError, loop_wav, validate_audio, validate_image, wav_speech_seconds  # noqa: E402
from .insurance_data import CLAIMS, POLICYHOLDERS, SYNTHETIC_NOTICE  # noqa: E402
from .db import AuditEvent, DecisionRow, FaceResultRow, FindingRow, Identity, Investigation, ProviderResultRow, SessionLocal, TrustedContact, init_db  # noqa: E402
from .detectify_provider import CAPABILITIES, provider  # noqa: E402
from .schemas import FaceFrame, InvestigationRequest, ProviderResult, ProviderStatus, RequestedAction, new_id  # noqa: E402

def _clean_token(raw: Optional[str]) -> str:
    """Same normalisation as the Next.js proxy: hosting dashboards often add spaces, newlines or quotes."""
    t = (raw or "").strip().strip("'\"").strip()
    return t or "ghostkey-dev-token"


API_TOKEN = _clean_token(os.getenv("GHOSTKEY_API_TOKEN"))
_fp = lambda t: hashlib.sha256((t or "").encode()).hexdigest()[:8]  # noqa: E731  (fingerprint for logs, never the token)
print(f"[ghostkey] backend internal token fingerprint: {_fp(API_TOKEN)}", flush=True)
MIN_ENROLL_SPEECH_SECONDS = 3.0  # real speech required in the original sample before it may be repeated
QUICK_ENROLL_MIN_SECONDS = 3.0  # short samples are repeated up to DetectifAI's 15 s enrollment minimum
app = FastAPI(title="GHOSTKEY 2.0", version="2.0.0")


def auth(x_ghostkey_token: Optional[str] = Header(default=None)):
    if not hmac.compare_digest((x_ghostkey_token or "").strip(), API_TOKEN):
        print(f"[ghostkey] rejected request: token fingerprint {_fp((x_ghostkey_token or '').strip()) if x_ghostkey_token else 'none'} "
              f"≠ backend {_fp(API_TOKEN)}", flush=True)
        raise HTTPException(status_code=401, detail="missing or invalid X-GhostKey-Token")


RETENTION_DAYS = float(os.getenv("GHOSTKEY_CASE_RETENTION_DAYS", "7"))


@app.exception_handler(UploadError)
def upload_error(_req, exc: UploadError):
    return JSONResponse(status_code=exc.status, content={"detail": exc.message, "code": exc.code, "report_id": getattr(exc, "report_id", None)})


@app.on_event("startup")
def startup():
    init_db()
    test_reports.mark_interrupted()
    _seed()
    _purge_old_cases()


def _delete_case(db, iid: str) -> bool:
    row = db.get(Investigation, iid)
    if not row:
        return False
    db.delete(row)
    for model in (ProviderResultRow, FaceResultRow, FindingRow, DecisionRow):
        db.query(model).filter(model.investigation_id == iid).delete()
    return True


def _purge_old_cases():
    cutoff = time.time() - RETENTION_DAYS * 86400
    with SessionLocal() as db:
        old = [r.id for r in db.query(Investigation).filter(Investigation.created_at < cutoff).all()]
        for iid in old:
            _delete_case(db, iid)
        db.commit()
    if old:
        audit_service.record("retention.purged", "cases", {"count": len(old), "retention_days": RETENTION_DAYS})


EXTRA_IDENTITIES = [
    # family: protected people
    ("id-ravi", "Ravi Menon (protected grandfather)", "family", "+91 94460 XXXXX", "Recovery email r.menon@example.com", "Ravi's phone"),
    ("id-sunita", "Sunita Iyer (protected mother)", "family", "+91 98860 XXXXX", "Recovery email s.iyer@example.com", "Sunita's phone"),
    ("id-joseph", "Joseph D'Souza (protected father)", "family", "+91 97390 XXXXX", "Daughter's verified number", "Joseph's phone"),
    ("id-fatima-s", "Fatima Sheikh (protected grandmother)", "family", "+91 99000 XXXXX", "Son's verified email", "Fatima's tablet"),
    # exam: students (enroll a face on the Exam page)
    ("id-ananya-s", "Ananya Sharma (student)", "exam", "", "University email", ""),
    ("id-karthik", "Karthik Rao (student)", "exam", "", "University email", ""),
    ("id-meera", "Meera Pillai (student)", "exam", "", "University email", ""),
    ("id-farhan", "Farhan Ali (student)", "exam", "", "University email", ""),
    ("id-nisha", "Nisha Gowda (student)", "exam", "", "University email", ""),
    ("id-judge", "Judge / guest tester (student)", "exam", "", "—", ""),
    # banking: customers
    ("id-ishaan", "Ishaan Malhotra (bank customer)", "banking", "+91 90000 00002", "Registered email", "Ishaan's registered phone"),
    ("id-ritu", "Ritu Chawla (bank customer)", "banking", "+91 90000 00003", "Registered email", "Ritu's registered phone"),
    ("id-naveen", "Naveen Krishnan (bank customer)", "banking", "+91 90000 00004", "Registered email", "Naveen's registered phone"),
    ("id-sara", "Sara Thomas (bank customer)", "banking", "+91 90000 00005", "Registered email", "Sara's registered phone"),
    ("id-guest", "Judge / guest customer", "banking", "", "—", "Guest's phone (simulated)"),
]
EXTRA_CONTACTS = {
    "id-ravi": [("Arun Menon", "son", "+91 94470 XXXXX"), ("Lakshmi Menon", "granddaughter", "+91 98950 XXXXX")],
    "id-sunita": [("Rohit Iyer", "son", "+91 98450 XXXXX (number recently changed)")],
    "id-joseph": [("Maria D'Souza", "daughter", "+91 97410 XXXXX"), ("Neil D'Souza", "son", "+91 99860 XXXXX")],
    "id-fatima-s": [("Imran Sheikh", "son", "+91 99001 XXXXX")],
}


SEEDED_IDS = {row[0] for row in EXTRA_IDENTITIES} | {"id-asha", "id-rahul", "id-zira"}


def _seed():
    with SessionLocal() as db:
        for iid, name, uc, phone, rec, dev in EXTRA_IDENTITIES:
            if not db.get(Identity, iid):
                db.add(Identity(id=iid, name=name, use_case=uc, phone=phone, recovery_method=rec, trusted_device=dev))
                for cname, rel, cphone in EXTRA_CONTACTS.get(iid, []):
                    db.add(TrustedContact(identity_id=iid, name=cname, relation=rel, phone=cphone))
        db.commit()
        if db.get(Identity, "id-zira"):
            return
        db.add_all([
            Identity(id="id-asha", name="Asha Rao (protected parent)", use_case="family", phone="+91 98450 XXXXX", recovery_method="Recovery email a.rao@example.com",
                     speaker_id="", speaker_enrolled=False, trusted_device="Asha's phone"),
            Identity(id="id-rahul", name="Rahul Verma (student)", use_case="exam", recovery_method="University email"),
            Identity(id="id-zira", name="Zira Rao (bank customer)", use_case="banking", phone="+91 90000 00001", recovery_method="Registered email",
                     speaker_id=scenarios.LIVE_SPEAKER_ID, speaker_enrolled=True, trusted_device="Zira's registered phone"),
        ])
        db.add_all([TrustedContact(identity_id="id-asha", name="Rohan Rao", relation="son", phone="+91 98450 XXXXX (old number, retired)"),
                    TrustedContact(identity_id="id-asha", name="Meera Rao", relation="daughter", phone="+91 99000 XXXXX")])
        db.commit()


def _identity_dict(i: Identity) -> dict:
    return {"id": i.id, "name": i.name, "use_case": i.use_case, "phone": i.phone, "recovery_method": i.recovery_method, "speaker_id": i.speaker_id,
            "speaker_enrolled": i.speaker_enrolled, "face_reference_enrolled": bool(i.face_embedding), "face_consent": i.face_consent, "trusted_device": i.trusted_device,
            "added": i.id not in SEEDED_IDS}


# ---------- status ----------
@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/provider/status", dependencies=[Depends(auth)])
def provider_status():
    h = provider.health()
    c = provider.credits() if provider.api_key else {"error": "DETECTIFAI_API_KEY not configured"}
    return {"provider": "detectify_ai", "key_configured": bool(provider.api_key), "health": h, "credits": c, "capabilities": CAPABILITIES,
            "face_model": {**face_service.MODEL_INFO, "available": face_service.available()}, "llm": "none configured — agents are deterministic and versioned",
            "n8n": "not connected — the same workflow runs in FastAPI (orchestrator.py)"}


# ---------- scenarios ----------
@app.get("/api/scenarios", dependencies=[Depends(auth)])
def list_scenarios():
    return [{"id": k, **v} for k, v in scenarios.SCENARIOS.items()]


@app.post("/api/scenarios/{sid}/run", dependencies=[Depends(auth)])
def run_scenario(sid: str, live: bool = False):
    if sid not in scenarios.SCENARIOS:
        raise HTTPException(404, "unknown scenario")
    return scenarios.run(sid, live and scenarios.SCENARIOS[sid]["live"])


# ---------- investigations & audit ----------
@app.get("/api/investigations", dependencies=[Depends(auth)])
def list_investigations(limit: int = 50):
    with SessionLocal() as db:
        rows = db.query(Investigation).order_by(Investigation.created_at.desc()).limit(limit).all()
        return [{"id": r.id, "use_case": r.use_case, "scenario_id": r.scenario_id, "title": r.title, "outcome": r.outcome, "created_at": r.created_at} for r in rows]


@app.get("/api/investigations/{iid}", dependencies=[Depends(auth)])
def get_investigation(iid: str):
    with SessionLocal() as db:
        r = db.get(Investigation, iid)
        if not r:
            raise HTTPException(404, "not found")
        return r.to_dict()


@app.get("/api/audit", dependencies=[Depends(auth)])
def audit():
    return {"integrity": audit_service.verify_chain(), "events": audit_service.recent()}


# ---------- identities ----------
@app.get("/api/identities", dependencies=[Depends(auth)])
def identities():
    with SessionLocal() as db:
        out = []
        for i in db.query(Identity).all():
            d = _identity_dict(i)
            d["trusted_contacts"] = [{"name": t.name, "relation": t.relation, "phone": t.phone} for t in db.query(TrustedContact).filter_by(identity_id=i.id)]
            out.append(d)
        return out


@app.post("/api/identities", dependencies=[Depends(auth)])
def create_identity(name: str = Form(...), use_case: str = Form(...), phone: str = Form(""), recovery_method: str = Form(""), trusted_device: str = Form("")):
    with SessionLocal() as db:
        i = Identity(id=new_id("id"), name=name, use_case=use_case, phone=phone, recovery_method=recovery_method, trusted_device=trusted_device)
        db.add(i)
        db.commit()
        audit_service.record("identity.created", i.id, {"use_case": use_case})
        return _identity_dict(i)


@app.post("/api/identities/{iid}/contacts", dependencies=[Depends(auth)])
def add_contact(iid: str, name: str = Form(...), relation: str = Form(...), phone: str = Form("")):
    with SessionLocal() as db:
        db.add(TrustedContact(identity_id=iid, name=name, relation=relation, phone=phone))
        db.commit()
    return {"ok": True}


@app.post("/api/identities/{iid}/face", dependencies=[Depends(auth)])
async def enroll_face(iid: str, consent: bool = Form(...), image: UploadFile = File(...)):
    if not consent:
        raise HTTPException(400, "consent is required to enroll a reference image")
    img = await image.read()
    validate_image(image.filename or 'reference.jpg', image.content_type, img)
    out = face_service.embed(img)
    if not out["ok"]:
        raise HTTPException(422, out["reason"] + f" (faces found: {out['faces']})")
    with SessionLocal() as db:
        i = db.get(Identity, iid)
        if not i:
            raise HTTPException(404, "unknown identity")
        i.face_embedding, i.face_consent = out["embedding"], True
        db.commit()
    audit_service.record("face.reference_enrolled", iid, {"model": face_service.MODEL_INFO["name"], "image_stored": False})
    return {"ok": True, "detection_score": out["detection_score"], "image_stored": False}


@app.post("/api/identities/{iid}/voice", dependencies=[Depends(auth)])
async def enroll_voice(iid: str, audio: UploadFile = File(...), append: bool = Form(False)):
    """Enroll (or re-enroll) a voiceprint. Re-enrolling REPLACES the previous DetectifAI voiceprint unless `append`
    is set: DetectifAI adds every enroll call as another sample of the same speaker, so re-enrolling someone with a
    different voice used to blend two people into one voiceprint (and both then matched)."""
    data = await audio.read()
    filename, ctype = audio.filename or "enroll.wav", audio.content_type or "audio/wav"
    with SessionLocal() as db:
        i = db.get(Identity, iid)
        if not i:
            raise HTTPException(404, "unknown identity")
        name, speaker_id, had_voiceprint = i.name, i.speaker_id or i.id, bool(i.speaker_enrolled and i.speaker_id)
    run = test_reports.start("speaker_enrollment", f"Speaker enrollment · {name}", endpoint="POST /api/identities/{id}/voice", provider="DetectifAI",
                             speaker_id=speaker_id, expected={"description": "DetectifAI accepts the sample and stores a voiceprint"})
    run.set_ids(case_id=iid)

    def reject(code: str, message: str, status: str = "FAIL", http: int = 422):
        run.step("validate audio", "failed", message)
        run.finish(status, summary=f"Enrollment not performed: {message}", reason=message, execution_status="completed" if status == "FAIL" else "error",
                   failure_stage="validate audio", retry_eligible=True, next_step="Record again: about 10 s of clear speech, close to the microphone.",
                   acceptance=[{"criterion": "sample meets enrollment requirements", "satisfied": False, "actual": message}])
        err = UploadError(code, message, http)
        err.report_id = run.id  # type: ignore[attr-defined]
        raise err

    try:
        meta = validate_audio(filename, ctype, data, for_deepfake=False)
    except UploadError as e:
        run.add_input(test_reports.audio_input(filename, ctype, data, truth="enrollment sample", consent=True))
        reject(e.code, e.message, http=e.status)
    recorded, looped = meta["duration_seconds"], None
    speech = wav_speech_seconds(data) if filename.lower().endswith(".wav") or ctype == "audio/wav" else None
    run.add_input(test_reports.audio_input(filename, ctype, data, {**meta, "speech_seconds": speech}, truth="enrollment sample", consent=True))
    if recorded is not None and not (QUICK_ENROLL_MIN_SECONDS <= recorded <= 60):
        reject("bad_duration", f"Enrollment needs {QUICK_ENROLL_MIN_SECONDS:.0f}–60 s of audio (got {recorded:.1f} s).")
    if speech is not None and speech < MIN_ENROLL_SPEECH_SECONDS:
        reject("insufficient_speech", f"Only about {speech:.1f} s of speech detected — at least {MIN_ENROLL_SPEECH_SECONDS:.0f} s is needed. "
                                      "Check the microphone (it may be muted or the wrong device) and speak for about 10 s.")
    run.step("validate audio", "completed", f"{recorded:.1f} s, ~{speech:.1f} s of speech" if recorded and speech is not None else "format accepted")
    if recorded is not None and recorded < 15:
        # DetectifAI's enroll endpoint needs 15–60 s; a shorter sample is repeated up to 16 s (stated in the result).
        data, looped = loop_wav(data, 16.0)
        run.step("extend short sample", "completed", f"{recorded:.1f} s repeated to {looped:.1f} s (DetectifAI minimum 15 s)")
    if had_voiceprint and not append:
        try:
            provider.delete_speaker(speaker_id)
            run.step("DetectifAI DELETE /v1/speakers/{id}", "completed", f"previous voiceprint {speaker_id} removed so samples are not blended")
        except Exception as e:  # not fatal: a missing speaker is fine, anything else is recorded
            run.step("DetectifAI DELETE /v1/speakers/{id}", "skipped", f"could not delete previous voiceprint: {getattr(e, 'message', e)}")
        with SessionLocal() as db:  # until the new enrollment succeeds this person has no usable voiceprint
            i = db.get(Identity, iid)
            i.speaker_enrolled = False
            db.commit()
    t = time.time()
    try:
        res = provider.enroll_speaker(data, speaker_id, name, filename=filename, content_type=ctype)
    except Exception as e:  # ProviderError — never store a fake enrollment
        code = getattr(e, "code", "error")
        run.step("DetectifAI POST /v1/speakers/enroll", "failed", f"{code}: {getattr(e, 'message', e)}", started=t)
        status = test_reports.provider_error_status(code, getattr(e, "status", None))
        run.finish("FAIL" if status == "HOLD" else "ERROR", summary=f"DetectifAI rejected the enrollment: {getattr(e, 'message', e)}",
                   execution_status="completed" if status == "HOLD" else "error", failure_stage="DetectifAI enroll", retry_eligible=True,
                   next_step="Re-record with more clear speech." if status == "HOLD" else "Check DetectifAI connectivity/credits and retry.",
                   acceptance=[{"criterion": "DetectifAI stores the voiceprint", "satisfied": False, "actual": code}])
        raise HTTPException(502, {"message": f"DetectifAI enrollment failed: {getattr(e, 'message', e)}", "code": code, "report_id": run.id})
    run.step("DetectifAI POST /v1/speakers/enroll", "completed", f"speaker_id={speaker_id}, samples={(res.get('speaker') or {}).get('samples')}",
             started=t, request_id=res.get("request_id"), operation_id=res.get("operation_id"))
    with SessionLocal() as db:
        i = db.get(Identity, iid)
        i.speaker_id, i.speaker_enrolled = speaker_id, True
        db.commit()
    run.step("persist enrollment", "completed", f"identity {iid} → DetectifAI speaker_id {speaker_id}")
    audit_service.record("voice.enrolled", iid, {"speaker_id": speaker_id, "operation": res.get("operation_id"), "recorded_seconds": recorded,
                                                 "looped_to_seconds": looped, "replaced_previous": had_voiceprint and not append})
    run.evidence(provider_response={"speaker": res.get("speaker"), "quality": res.get("quality"), "operation_id": res.get("operation_id"), "model": res.get("model")})
    run.finish("PASS", summary=f"Voiceprint enrolled for {name}", verification_outcome="ENROLLED", actual={"speaker": res.get("speaker"), "quality": res.get("quality")},
               acceptance=[{"criterion": "sample meets requirements", "satisfied": True, "actual": f"{recorded} s"},
                           {"criterion": "DetectifAI stores the voiceprint", "satisfied": True, "actual": (res.get("speaker") or {}).get("speaker_id")}])
    return {"ok": True, "identity_id": iid, "name": name, "speaker_id": speaker_id, "speaker": res.get("speaker"), "quality": res.get("quality"),
            "operation_id": res.get("operation_id"), "recorded_seconds": recorded, "speech_seconds": speech, "looped_to_seconds": looped,
            "replaced_previous": had_voiceprint and not append, "report_id": run.id,
            "note": (f"Your {recorded:.1f} s sample was repeated to {looped:.0f} s to meet DetectifAI's 15 s enrollment minimum. "
                     "A 15 s sample of varied speech gives a stronger voiceprint.") if looped else None}


@app.delete("/api/identities/{iid}", dependencies=[Depends(auth)])
def delete_identity(iid: str):
    """Remove a person added during testing, with their face embedding and DetectifAI voiceprint. Seeded people stay."""
    if iid in SEEDED_IDS:
        raise HTTPException(400, "built-in demo people cannot be deleted")
    with SessionLocal() as db:
        i = db.get(Identity, iid)
        if not i:
            raise HTTPException(404, "unknown identity")
        voice_deleted = None
        if i.speaker_enrolled and i.speaker_id:
            try:
                provider.delete_speaker(i.speaker_id)
                voice_deleted = True
            except Exception:  # still remove locally; the voiceprint can be removed in DetectifAI's dashboard
                voice_deleted = False
        db.query(TrustedContact).filter_by(identity_id=iid).delete()
        db.delete(i)
        db.commit()
    audit_service.record("identity.deleted", iid, {"voiceprint_deleted": voice_deleted})
    return {"ok": True, "voiceprint_deleted": voice_deleted}


# ---------- local downloads (judge picks a file they just downloaded) ----------
LOCAL_DOWNLOADS = os.getenv("GHOSTKEY_LOCAL_DOWNLOADS", "1") == "1"
DOWNLOADS_DIR = os.path.expanduser(os.getenv("GHOSTKEY_DOWNLOADS_DIR", os.path.join("~", "Downloads")))


def _download_files(limit: int = 12) -> list[dict]:
    if not (LOCAL_DOWNLOADS and os.path.isdir(DOWNLOADS_DIR)):
        return []
    now, out = time.time(), []
    with os.scandir(DOWNLOADS_DIR) as it:
        for e in it:
            if e.is_file() and os.path.splitext(e.name)[1].lower() in AUDIO_EXT:
                st = e.stat()
                out.append({"name": e.name, "bytes": st.st_size, "modified": st.st_mtime, "age_seconds": round(now - st.st_mtime)})
    return sorted(out, key=lambda f: -f["modified"])[:limit]


@app.get("/api/local/downloads", dependencies=[Depends(auth)])
def local_downloads():
    return {"enabled": LOCAL_DOWNLOADS, "folder": DOWNLOADS_DIR if LOCAL_DOWNLOADS else None, "files": _download_files()}


@app.get("/api/local/downloads/file", dependencies=[Depends(auth)])
def local_download_file(name: str):
    # only an audio file that is currently listed in the Downloads folder — no paths, no other folders
    if not LOCAL_DOWNLOADS or os.path.basename(name) != name or name not in {f["name"] for f in _download_files(200)}:
        raise HTTPException(404, "file not found in Downloads")
    path = os.path.join(DOWNLOADS_DIR, name)
    if os.path.getsize(path) > MAX_AUDIO_MB * 1_000_000:
        raise HTTPException(413, f"File exceeds {MAX_AUDIO_MB:.0f} MB")
    return FileResponse(path, media_type="application/octet-stream")


# ---------- audio analysis ----------
@app.post("/api/audio/analyze", dependencies=[Depends(auth)])
async def analyze_audio(audio: UploadFile = File(...), expected: str = Form("")):
    """Deepfake check. Acceptance: the audio is judged human — unless the tester declares what it really is
    (`expected` = real_human | ai_voice), in which case PASS means DetectifAI agreed with that label."""
    data = await audio.read()
    filename, ctype = audio.filename or "audio.wav", audio.content_type or "audio/wav"
    exp = {"real_human": "real", "ai_voice": "fake"}.get(expected)
    run = test_reports.start("voice_deepfake", f"Voice deepfake detection · {filename}", endpoint="POST /api/audio/analyze", provider="DetectifAI",
                             expected={"evidence": expected, "description": f"DetectifAI verdict '{exp}'"} if exp else
                             {"description": "audio judged human (no synthetic indicators)"})
    try:
        meta = validate_audio(filename, ctype, data)
    except UploadError as e:
        run.add_input(test_reports.audio_input(filename, ctype, data))
        run.step("validate audio", "failed", e.message)
        run.finish("ERROR", summary=f"Audio rejected before analysis: {e.message}", execution_status="error", failure_stage="validate audio", retry_eligible=True,
                   next_step="Use a supported audio file of more than 4 s and at most 120 s.")
        e.report_id = run.id  # type: ignore[attr-defined]
        raise
    run.add_input(test_reports.audio_input(filename, ctype, data, meta, truth=expected or "unknown"))
    run.step("validate audio", "completed", f"{meta['duration_seconds']:.1f} s" if meta["duration_seconds"] else "format accepted")
    t = time.time()
    result = provider.audio_authenticity(data, filename=filename, content_type=ctype)
    det = result.details or {}
    run.step("DetectifAI POST /v1/deepfake/detect", "completed" if result.status.value in ("COMPLETED", "INCONCLUSIVE") else "failed",
             result.classification or result.error or result.status.value, started=t, request_id=det.get("request_id"), operation_id=result.raw_result_reference)
    req = InvestigationRequest(use_case="banking", requested_action=RequestedAction(type="balance_enquiry"), audio_authenticity=result)
    finding = voice_authenticity_agent.analyze(req)
    run.step("voice_authenticity_agent", "completed", finding.status.value)
    audit_service.record("audio.analyzed", filename, {"status": result.status.value, "classification": result.classification, "report_id": run.id})
    run.evidence(provider_result={"status": result.status.value, "verdict": result.classification, "score": result.score, "threshold": result.threshold,
                                  "score_semantics": result.score_semantics, "segments": det.get("segments"), "model": det.get("model"),
                                  "operation_id": result.raw_result_reference, "request_id": det.get("request_id"), "error": result.error},
                 agent_finding={"status": finding.status.value, "next_step": finding.recommended_next_step}, uncertainty=result.limitations)
    if result.status.value in ("UNAVAILABLE", "FAILED"):
        st = test_reports.provider_error_status((result.error or "").split(":")[0], result.status.value)
        run.finish(st, summary=f"DetectifAI could not analyse the audio: {result.error}", verification_outcome="NOT_ANALYSED",
                   execution_status="completed" if st == "HOLD" else "error", failure_stage="DetectifAI deepfake detect", retry_eligible=True,
                   next_step="Retry with clearer / longer speech." if st == "HOLD" else "Check connectivity and credits, then retry.")
    else:
        verdict = result.classification
        if exp:
            ok = verdict == exp
            status, basis = ("PASS" if ok else ("HOLD" if verdict == "not_sure" else "FAIL")), "expected_vs_actual"
        else:
            status, basis = {"real": "PASS", "fake": "FAIL"}.get(verdict, "HOLD"), "acceptance_criteria"
        run.finish(status, summary={"real": "No synthetic indicators", "fake": "Synthetic (AI-generated) indicators", "not_sure": "Inconclusive"}.get(verdict, str(verdict)),
                   verification_outcome=str(verdict).upper(), actual={"verdict": verdict, "score": result.score, "threshold": result.threshold}, status_basis=basis,
                   acceptance=[{"criterion": f"verdict is '{exp or 'real'}'", "satisfied": verdict == (exp or "real"), "actual": verdict}],
                   next_step=finding.recommended_next_step)
    return {"upload": meta, "provider_result": result.model_dump(), "voice_agent_finding": finding.model_dump(), "report_id": run.id}


# ---------- sessions, challenges, approvals ----------
@app.post("/api/sessions", dependencies=[Depends(auth)])
def create_session(payload: dict):
    s = session_service.create_session(payload["use_case"], payload.get("identity_id"), payload["action"])
    return {**s, "challenge": session_service.issue_challenge(s["session_id"])}


@app.post("/api/sessions/{sid}/challenge", dependencies=[Depends(auth)])
def new_challenge(sid: str):
    return session_service.issue_challenge(sid)


@app.post("/api/sessions/{sid}/challenge/verify", dependencies=[Depends(auth)])
def verify_challenge(sid: str, payload: dict):
    return session_service.verify_challenge(sid, payload["challenge_id"], payload["response"])


@app.post("/api/sessions/{sid}/approval", dependencies=[Depends(auth)])
def request_approval(sid: str, payload: dict):
    return session_service.request_approval(sid, payload["action"], payload["device"])


@app.post("/api/approvals/{aid}/decide", dependencies=[Depends(auth)])
def decide_approval(aid: str, payload: dict):
    return session_service.decide_approval(aid, bool(payload.get("approve")), payload["device"])


# ---------- live investigations (banking & family) ----------
@app.post("/api/investigate", dependencies=[Depends(auth)])
async def investigate(
    use_case: str = Form(...), identity_id: str = Form(...), action: str = Form(...), actor_role: str = Form("customer"),
    transcript: str = Form(""), challenge_check: str = Form(""), approval_id: str = Form(""), carrier_events: str = Form("[]"),
    account_events: str = Form("[]"), independent_verification: str = Form(""), audio: Optional[UploadFile] = File(None),
):
    act = RequestedAction(**json.loads(action))
    with SessionLocal() as db:
        ident = db.get(Identity, identity_id)
        if not ident:
            raise HTTPException(404, "unknown identity")
        speaker_id, enrolled = ident.speaker_id, ident.speaker_enrolled
    audio_res = speaker_res = None
    run = test_reports.start(orchestrator.CATEGORY.get(use_case, use_case), f"Live {use_case}: {act.type}", feature=use_case, endpoint="POST /api/investigate",
                             provider="DetectifAI" if audio is not None else None, speaker_id=speaker_id or None)
    if audio is not None:
        data = await audio.read()
        try:
            meta = validate_audio(audio.filename or "call.wav", audio.content_type, data)
        except UploadError as e:
            run.add_input(test_reports.audio_input(audio.filename or "call.wav", audio.content_type, data))
            run.error(e.message, "validate audio", summary=f"Audio rejected: {e.message}")
            e.report_id = run.id  # type: ignore[attr-defined]
            raise
        run.add_input(test_reports.audio_input(audio.filename or "call.wav", audio.content_type, data, meta, consent=True))
        run.step("validate audio", "completed", "accepted")
        if enrolled and speaker_id:
            speaker_res, audio_res = provider.speaker_verification(data, speaker_id, filename=audio.filename or "call.wav", content_type=audio.content_type or "audio/wav")
            audio_res = audio_res or provider.audio_authenticity(data, filename=audio.filename or "call.wav", content_type=audio.content_type or "audio/wav")
        else:
            audio_res = provider.audio_authenticity(data, filename=audio.filename or "call.wav", content_type=audio.content_type or "audio/wav")
    req = InvestigationRequest(
        use_case=use_case, identity_id=identity_id, claimed_identity=ident.name, actor_role=actor_role, requested_action=act, transcript=transcript or None,
        audio_authenticity=audio_res, speaker_verification=speaker_res, speaker_reference_enrolled=enrolled,
        challenge_check=json.loads(challenge_check) if challenge_check else None,
        approval_check=session_service.check_approval(approval_id or None, act.model_dump()) if use_case == "banking" else None,
        carrier_events=json.loads(carrier_events), account_events=json.loads(account_events),
        independent_verification=json.loads(independent_verification) if independent_verification else None,
        title=f"Live {use_case}: {act.type}",
    )
    return orchestrator.run(req, report=run)


# ---------- exam ----------
@app.post("/api/exam/verify", dependencies=[Depends(auth)])
async def exam_verify(identity_id: str = Form(...), frames: list[UploadFile] = File(...), threshold: float = Form(face_service.THRESHOLD)):
    if not (0.2 <= threshold <= 0.7):
        raise HTTPException(422, "threshold must be between 0.2 and 0.7 (OpenCV's published SFace value is 0.363)")
    with SessionLocal() as db:
        ident = db.get(Identity, identity_id)
        if not ident:
            raise HTTPException(404, "unknown identity")
        ref = ident.face_embedding
    if not face_service.available():
        raise HTTPException(503, "face model files missing")
    analysed = []
    run = test_reports.start("face_verification", f"Live exam check: {ident.name}", feature="exam", endpoint="POST /api/exam/verify", provider="OpenCV YuNet + SFace (local)")
    run.set_ids(case_id=identity_id)
    run.add_input({"kind": "images", "frames_submitted": len(frames), "reference_enrolled": bool(ref), "threshold": threshold, "consent": bool(ref),
                   "note": "frames analysed in memory; only similarity scores are kept"})
    for i, fr in enumerate(frames):
        try:
            raw = await fr.read()
            validate_image(fr.filename or f"frame{i}.jpg", fr.content_type, raw)
            analysed.append(FaceFrame(**face_service.analyze_frame(raw, ref, i)))
        except ValueError:
            continue
    req = InvestigationRequest(use_case="exam", identity_id=identity_id, claimed_identity=ident.name, actor_role="student",
                               requested_action=RequestedAction(type="start_exam"), face_frames=analysed, face_reference_enrolled=bool(ref),
                               face_model={**face_service.MODEL_INFO, "threshold": threshold, "threshold_is_default": threshold == face_service.THRESHOLD}, title=f"Live exam check: {ident.name}")
    run.step("face model", "completed", f"{len(analysed)} of {len(frames)} frame(s) analysed")
    return orchestrator.run(req, report=run)


# ---------- deletion controls ----------
@app.delete("/api/investigations/{iid}", dependencies=[Depends(auth)])
def delete_investigation(iid: str):
    with SessionLocal() as db:
        if not _delete_case(db, iid):
            raise HTTPException(404, "not found")
        db.commit()
    audit_service.record("case.deleted", iid, {})
    return {"ok": True}


@app.delete("/api/identities/{iid}/face", dependencies=[Depends(auth)])
def delete_face(iid: str):
    with SessionLocal() as db:
        i = db.get(Identity, iid)
        if not i:
            raise HTTPException(404, "unknown identity")
        i.face_embedding, i.face_consent = None, False
        db.query(FaceResultRow).filter(FaceResultRow.investigation_id.in_(
            [r.id for r in db.query(Investigation).filter(Investigation.use_case == "exam").all() if json.loads(r.record)["request"].get("identity_id") == iid])).delete(synchronize_session=False)
        db.commit()
    audit_service.record("face.reference_deleted", iid, {})
    return {"ok": True}


# ---------- speaker verification ----------
@app.post("/api/speakers/verify", dependencies=[Depends(auth)])
async def speakers_verify(identity_id: str = Form(...), audio: UploadFile = File(...), expected: str = Form(""), attempt_id: str = Form("")):
    """Verify one recording against ONE enrolled person's voiceprint.
    Verification outcome: MATCH | NO_MATCH | INCONCLUSIVE | NOT_VERIFIED (provider error / unusable audio).
    Test status: without an expectation PASS = identity confirmed, FAIL = identity rejected; with
    `expected` = same_person | different_person, PASS = DetectifAI's decision agreed with the tester's label."""
    attempt_id = attempt_id or new_id("att")
    data = await audio.read()
    filename, ctype = audio.filename or "audio.wav", audio.content_type or "audio/wav"
    exp_decision = {"same_person": "match", "different_person": "no_match"}.get(expected)
    run = test_reports.start("speaker_verification", "Speaker verification", endpoint="POST /api/speakers/verify", provider="DetectifAI",
                             expected={"evidence": expected, "description": f"DetectifAI decision '{exp_decision}'"} if exp_decision else
                             {"description": "claimed identity confirmed (decision 'match')"})
    run.set_ids(attempt_id=attempt_id, case_id=identity_id)
    with SessionLocal() as db:
        ident = db.get(Identity, identity_id)
        name = ident.name if ident else None
        speaker_id = ident.speaker_id if ident else None
        enrolled = bool(ident and ident.speaker_enrolled and ident.speaker_id)
    run.data["test"]["name"] = f"Speaker verification · {name or identity_id}"
    if not ident:
        run.step("lookup enrolled speaker", "failed", f"identity {identity_id} does not exist")
        run.finish("SKIPPED", summary="Not run: the selected person does not exist.", verification_outcome="NOT_RUN", execution_status="completed",
                   next_step="Pick an existing person or add one first.")
        raise HTTPException(404, {"message": "unknown identity", "report_id": run.id})
    run.set_ids(speaker_id=speaker_id)
    try:
        meta = validate_audio(filename, ctype, data, for_deepfake=False)
    except UploadError as e:
        run.add_input(test_reports.audio_input(filename, ctype, data))
        run.step("validate audio", "failed", e.message)
        run.finish("ERROR", summary=f"Audio rejected before verification: {e.message}", verification_outcome="NOT_VERIFIED", execution_status="error",
                   failure_stage="validate audio", retry_eligible=True, next_step="Use a supported audio file (3–60 s of speech).")
        e.report_id = run.id  # type: ignore[attr-defined]
        raise
    speech = wav_speech_seconds(data) if filename.lower().endswith(".wav") else None
    run.add_input(test_reports.audio_input(filename, ctype, data, {**meta, "speech_seconds": speech}, truth=expected or "unknown"))
    run.step("validate audio", "completed", f"{meta['duration_seconds']:.1f} s" if meta["duration_seconds"] else "format accepted")
    if not enrolled:
        run.step("lookup enrolled speaker", "failed", f"{name} has no enrolled voiceprint")
        run.finish("SKIPPED", summary=f"Not run: {name} has no enrolled voiceprint.", verification_outcome="NOT_RUN", next_step="Enroll a voiceprint first.")
        return {"upload": meta, "speaker_result": None, "deepfake_result": None, "status": "NOT_ENROLLED", "detail": "Enroll a voice sample first.",
                "attempt_id": attempt_id, "report_id": run.id}
    run.step("lookup enrolled speaker", "completed", f"{name} → DetectifAI speaker_id {speaker_id}")
    deepfake_wanted = meta["duration_seconds"] is None or meta["duration_seconds"] > 4
    t = time.time()
    spk, df = provider.speaker_verification(data, speaker_id, filename=filename, content_type=ctype, detect_deepfake=deepfake_wanted)
    det = spk.details or {}
    run.step("DetectifAI POST /v1/speakers/verify", "completed" if spk.status.value == "COMPLETED" else "failed",
             f"speaker_id sent={speaker_id}; decision={spk.classification or spk.error}", started=t, request_id=det.get("request_id"),
             operation_id=spk.raw_result_reference, detect_deepfake=deepfake_wanted)
    req = InvestigationRequest(use_case="banking", requested_action=RequestedAction(type="balance_enquiry"), speaker_verification=spk, speaker_reference_enrolled=True)
    finding = speaker_identity_agent.analyze(req)
    run.step("speaker_identity_agent", "completed", finding.status.value)
    audit_service.record("speaker.verified", identity_id, {"status": spk.status.value, "decision": spk.classification, "similarity": spk.score,
                                                           "attempt_id": attempt_id, "report_id": run.id})
    run.evidence(speaker_result={"status": spk.status.value, "decision": spk.classification, "similarity": spk.score, "threshold": spk.threshold,
                                 "score_semantics": spk.score_semantics, "speaker_id_sent": speaker_id, "speaker_id_returned": det.get("speaker_id"),
                                 "duration_seconds": det.get("duration_seconds"), "operation_id": spk.raw_result_reference, "request_id": det.get("request_id"),
                                 "model": det.get("model"), "error": spk.error},
                 deepfake_result={"status": df.status.value, "verdict": df.classification, "score": df.score, "threshold": df.threshold, "error": df.error} if df else
                 {"status": "NOT_RUN", "reason": "audio of 4 s or less" if not deepfake_wanted else "not returned"},
                 agent_finding={"status": finding.status.value, "next_step": finding.recommended_next_step},
                 note="Speaker verification (is this the claimed person?) and deepfake detection (is this AI audio?) are separate evidence.")
    if spk.status.value != "COMPLETED":
        st = test_reports.provider_error_status((spk.error or "").split(":")[0], spk.status.value)
        outcome = "NOT_VERIFIED"
        run.finish(st, summary=f"Could not verify: {spk.error}", verification_outcome=outcome, execution_status="completed" if st == "HOLD" else "error",
                   failure_stage="DetectifAI speaker verify", retry_eligible=True,
                   next_step="Record again with at least a few seconds of clear speech (check the mic level)." if st == "HOLD" else "Check DetectifAI connectivity and credits, then retry.",
                   hypotheses=["Microphone muted, wrong input device or very low input volume."] if "speech" in (spk.error or "") else None)
    else:
        outcome = {"SPEAKER_MATCH_SUPPORTED": "MATCH", "SPEAKER_MISMATCH_SUSPECTED": "NO_MATCH", "INCONCLUSIVE": "INCONCLUSIVE"}.get(finding.status.value, "INCONCLUSIVE")
        if exp_decision:
            ok = spk.classification == exp_decision and outcome != "INCONCLUSIVE"
            status, basis = ("PASS" if ok else ("HOLD" if outcome == "INCONCLUSIVE" else "FAIL")), "expected_vs_actual"
        else:
            status, basis = {"MATCH": "PASS", "NO_MATCH": "FAIL"}.get(outcome, "HOLD"), "acceptance_criteria"
        run.finish(status, summary={"MATCH": f"Match confirmed: voice matches {name}'s voiceprint", "NO_MATCH": f"Match rejected: voice does not match {name}'s voiceprint",
                                    "INCONCLUSIVE": "Inconclusive: similarity is close to the threshold"}[outcome],
                   verification_outcome=outcome, actual={"decision": spk.classification, "similarity": spk.score, "threshold": spk.threshold}, status_basis=basis,
                   acceptance=[{"criterion": f"DetectifAI decision is '{exp_decision or 'match'}'", "satisfied": spk.classification == (exp_decision or "match"), "actual": spk.classification},
                               {"criterion": "similarity not within ±0.05 of the threshold", "satisfied": outcome != "INCONCLUSIVE", "actual": spk.score}],
                   next_step=finding.recommended_next_step)
    return {"upload": meta, "speaker_result": spk.model_dump(), "deepfake_result": df.model_dump() if df else None,
            "speaker_agent_finding": finding.model_dump(), "verification_outcome": outcome, "attempt_id": attempt_id, "report_id": run.id,
            "identity": {"id": identity_id, "name": name, "speaker_id": speaker_id}, "submitted_audio_sha256": run.data["inputs"][0]["sha256"],
            "test_status": run.data["status"]}


# ---------- insurance (synthetic demo records) ----------
@app.get("/api/insurance/claims", dependencies=[Depends(auth)])
def insurance_claims():
    return {"notice": SYNTHETIC_NOTICE, "policyholders": list(POLICYHOLDERS.values()), "claims": list(CLAIMS.values())}


@app.post("/api/insurance/investigate", dependencies=[Depends(auth)])
async def insurance_investigate(claim_id: str = Form(...), actor_role: str = Form("policyholder"), transcript: str = Form(""), challenge_check: str = Form(""),
                                approval_id: str = Form(""), action_type: str = Form(""), new_payout_account: str = Form(""), audio: Optional[UploadFile] = File(None)):
    claim = CLAIMS.get(claim_id)
    if not claim:
        raise HTTPException(404, "unknown claim")
    claim = {**claim, "requested_action": action_type or claim["requested_action"], "new_payout_account": new_payout_account or claim["new_payout_account"]}
    ph = POLICYHOLDERS[claim["policyholder_id"]]
    act = RequestedAction(type=claim["requested_action"], amount=claim["amount"], details={"claim_id": claim_id, "new_payout_account": claim["new_payout_account"]})
    audio_res = speaker_res = None
    run = test_reports.start("insurance_claim", f"Live insurance: {claim_id} · {act.type}", feature="insurance", endpoint="POST /api/insurance/investigate",
                             provider="DetectifAI" if audio is not None else None)
    run.add_input({"kind": "claim", "claim_id": claim_id, "synthetic_record": True, "action": act.type})
    if audio is not None:
        data = await audio.read()
        try:
            meta = validate_audio(audio.filename or "call.wav", audio.content_type, data)
        except UploadError as e:
            run.error(e.message, "validate audio", summary=f"Audio rejected: {e.message}")
            e.report_id = run.id  # type: ignore[attr-defined]
            raise
        run.add_input(test_reports.audio_input(audio.filename or "call.wav", audio.content_type, data, meta, consent=True))
        if ph["voice_enrolled"] and ph["speaker_id"]:
            speaker_res, audio_res = provider.speaker_verification(data, ph["speaker_id"], filename=audio.filename or "call.wav", content_type=audio.content_type or "audio/wav")
        audio_res = audio_res or provider.audio_authenticity(data, filename=audio.filename or "call.wav", content_type=audio.content_type or "audio/wav")
    req = InvestigationRequest(use_case="insurance", identity_id=ph["id"], claimed_identity=claim["claimant"], actor_role=actor_role, requested_action=act,
                               transcript=transcript or None, audio_authenticity=audio_res, speaker_verification=speaker_res, speaker_reference_enrolled=ph["voice_enrolled"],
                               claim=claim, policyholder=ph, challenge_check=json.loads(challenge_check) if challenge_check else None,
                               approval_check=session_service.check_approval(approval_id or None, act.model_dump()), title=f"Live insurance: {claim_id} · {act.type}")
    return orchestrator.run(req, report=run)


# ---------- settings (configuration status only — never secrets) ----------
@app.get("/api/settings", dependencies=[Depends(auth)])
def settings():
    return {
        "detectifai": {"api_key_configured": bool(provider.api_key), "api_key_env_vars": ["DETECTIF_API_KEY", "DETECTIFAI_API_KEY"], "base_url": provider.base_url,
                       "capabilities": CAPABILITIES, "scopes_note": "Scopes are not exposed by the API; a 403 insufficient_scope response is reported if a scope is missing."},
        "internal_api_token_configured": API_TOKEN != "ghostkey-dev-token",
        "face_model": {**face_service.MODEL_INFO, "available": face_service.available()},
        "uploads": {"max_audio_mb": MAX_AUDIO_MB, "max_image_mb": MAX_IMAGE_MB, "stored_on_disk": False},
        "retention": {"case_retention_days": RETENTION_DAYS, "biometrics": "face references stored as embeddings only; raw images and audio are never stored"},
        "database": {"engine": "SQLite (SQLAlchemy)", "mongodb": "not configured — SQLite retained (documented in ARCHITECTURE.md)"},
        "llm": "none configured — agents are rule-based and versioned",
        "n8n": "not connected — orchestration runs in FastAPI",
        "trusted_device": "SIMULATED (on-screen device panel); no WebAuthn/passkeys",
    }


# ---------- real-human example library ----------
app.mount("/api/media", __import__("fastapi.staticfiles", fromlist=["StaticFiles"]).StaticFiles(directory=examples.EX_DIR), name="media")


@app.get("/api/examples/{use_case}", dependencies=[Depends(auth)])
def list_examples(use_case: str):
    if use_case not in ("exam", "family", "insurance", "banking"):
        raise HTTPException(404, "unknown use case")
    return examples.listing(use_case)


@app.post("/api/examples/{use_case}/{eid}/run", dependencies=[Depends(auth)])
def run_example(use_case: str, eid: str, live: bool = False):
    try:
        return examples.run(use_case, eid, live)
    except KeyError:
        raise HTTPException(404, "unknown example")


@app.get("/api/stats", dependencies=[Depends(auth)])
def stats():
    """Real counts from the database for the dashboard (no hard-coded metrics)."""
    with SessionLocal() as db:
        rows = db.query(Investigation.use_case, Investigation.outcome).all()
    by_outcome, by_use = {}, {}
    for uc, oc in rows:
        by_outcome[oc] = by_outcome.get(oc, 0) + 1
        by_use[uc] = by_use.get(uc, 0) + 1
    return {"total": len(rows), "by_outcome": by_outcome, "by_use_case": by_use, "audit": audit_service.verify_chain()}



# ---------- judge test: your own recording / AI clone in any scenario ----------
@app.post("/api/test/{use_case}", dependencies=[Depends(auth)])
async def judge_test(use_case: str, context_id: str = Form(...), transcript: str = Form(""), speaker_identity_id: str = Form(""), person_identity_id: str = Form(""), expected: str = Form(""), audio: UploadFile = File(...)):
    if use_case not in ("family", "insurance", "banking"):
        raise HTTPException(404, "voice tests are available for family, insurance and banking")
    data = await audio.read()
    try:
        return examples.run_custom(use_case, context_id, data, audio.filename or "recording.webm", audio.content_type or "audio/webm", transcript, speaker_identity_id, person_identity_id, expected)
    except KeyError:
        raise HTTPException(404, "unknown scenario context")
    except ValueError as e:
        if isinstance(e, UploadError):
            raise
        raise HTTPException(422, str(e))


# ---------- test reports ----------
@app.get("/api/reports", dependencies=[Depends(auth)])
def list_reports(status: str = "", category: str = "", q: str = "", provider_name: str = "", since: float = 0, until: float = 0,
                 sort: str = "-created_at", limit: int = 100, offset: int = 0):
    return test_reports.query(status=status, category=category, q=q, provider=provider_name, since=since, until=until, sort=sort, limit=limit, offset=offset)


@app.get("/api/reports/stats", dependencies=[Depends(auth)])
def report_stats():
    return test_reports.stats()


@app.get("/api/reports/{rid}", dependencies=[Depends(auth)])
def get_report(rid: str):
    r = test_reports.get(rid)
    if not r:
        raise HTTPException(404, "report not found")
    return r


@app.get("/api/reports/{rid}/export", dependencies=[Depends(auth)])
def export_report(rid: str):
    r = test_reports.get(rid)
    if not r:
        raise HTTPException(404, "report not found")
    return JSONResponse(r, headers={"Content-Disposition": f'attachment; filename="ghostkey-report-{rid}.json"'})


@app.post("/api/reports/connectivity", dependencies=[Depends(auth)])
def connectivity_check():
    """API integration / connectivity test (free: health + credits, no audio is sent)."""
    run = test_reports.start("connectivity", "DetectifAI connectivity check", endpoint="POST /api/reports/connectivity", provider="DetectifAI",
                             expected={"description": "API reachable, key accepted, credits available"})
    t = time.time()
    h = provider.health()
    run.step("GET /v1/health", "completed" if h.get("reachable") else "failed", str(h.get("status") or h.get("error")), started=t)
    t = time.time()
    c = provider.credits()
    run.step("GET /v1/credits", "failed" if c.get("error") else "completed", c.get("error") or f"{c.get('available')} credits available", started=t,
             request_id=c.get("request_id"))
    run.step("face model files", "completed" if face_service.available() else "failed", "loaded" if face_service.available() else "missing")
    crit = [{"criterion": "DetectifAI reachable", "satisfied": bool(h.get("reachable")), "actual": h.get("status") or h.get("error")},
            {"criterion": "API key accepted", "satisfied": not c.get("error"), "actual": c.get("code") or "ok"},
            {"criterion": "credits available", "satisfied": bool(c.get("unlimited") or (c.get("available") or 0) > 0), "actual": c.get("available")},
            {"criterion": "local face model loaded", "satisfied": face_service.available(), "actual": face_service.available()}]
    run.evidence(health={k: v for k, v in h.items() if k != "error"}, credits={k: c.get(k) for k in ("available", "plan", "price_per_operation", "unlimited", "code")})
    ok = all(x["satisfied"] for x in crit)
    run.finish("PASS" if ok else "ERROR", summary="All integrations reachable" if ok else "Integration problem: " + ", ".join(x["criterion"] for x in crit if not x["satisfied"]),
               acceptance=crit, execution_status="completed" if ok else "error", retry_eligible=not ok)
    return test_reports.get(run.id)


@app.post("/api/reports/selftest", dependencies=[Depends(auth)])
def run_backend_tests():
    """Run the automated backend suite (pytest, mocked provider — no credits) and store one report with every test case."""
    import subprocess
    import sys
    import tempfile
    import xml.etree.ElementTree as ET
    run = test_reports.start("automated_backend_tests", "Automated backend test suite (pytest)", endpoint="POST /api/reports/selftest", provider="none (mocked provider)",
                             expected={"description": "every test passes"})
    if os.getenv("GHOSTKEY_PUBLIC") == "1":  # public link: don't let visitors start CPU-heavy test runs on the host
        run.finish("SKIPPED", summary="Disabled on the public deployment (GHOSTKEY_PUBLIC=1). Run `pytest` locally instead.", execution_status="completed")
        raise HTTPException(403, {"message": "The backend test suite is disabled on the public deployment.", "report_id": run.id})
    backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    xml_path = os.path.join(tempfile.gettempdir(), f"ghostkey-pytest-{run.id}.xml")
    t = time.time()
    try:
        env = {k: v for k, v in os.environ.items() if k not in ("GHOSTKEY_DB",)}
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={xml_path}", "tests"], cwd=backend,
                              capture_output=True, text=True, timeout=300, env=env)
        root = ET.parse(xml_path).getroot()
    except Exception as e:
        run.error(e, "run pytest")
        return test_reports.get(run.id)
    cases = []
    for tc in root.iter("testcase"):
        st = "FAIL" if tc.find("failure") is not None else "ERROR" if tc.find("error") is not None else "SKIPPED" if tc.find("skipped") is not None else "PASS"
        node = tc.find("failure") if tc.find("failure") is not None else tc.find("error")
        cases.append({"name": tc.get("name"), "status": st, "seconds": float(tc.get("time") or 0), "message": (node.get("message") or "")[:300] if node is not None else None})
    for c in cases:
        run.data["execution"]["steps"].append({"name": c["name"], "status": {"PASS": "completed", "SKIPPED": "skipped"}.get(c["status"], "failed"),
                                               "detail": c["message"] or c["status"], "at_utc": None, "t_ms": None, "duration_ms": round(c["seconds"] * 1000), "data": None})
    counts = {k: sum(1 for c in cases if c["status"] == k) for k in ("PASS", "FAIL", "ERROR", "SKIPPED")}
    run.evidence(counts=counts, exit_code=proc.returncode, output_tail=proc.stdout[-1500:], note="Unit tests use a mocked DetectifAI provider; no live calls, no credits.")
    status = "PASS" if counts["FAIL"] == 0 and counts["ERROR"] == 0 and cases else ("ERROR" if not cases else "FAIL")
    run.step("pytest", "completed", f"{counts['PASS']} passed, {counts['FAIL']} failed, {counts['ERROR']} errors, {counts['SKIPPED']} skipped", started=t)
    run.finish(status, summary=f"{counts['PASS']}/{len(cases)} backend tests passed", acceptance=[{"criterion": "no failing tests", "satisfied": status == "PASS",
               "actual": counts}], actual=counts)
    return test_reports.get(run.id)


@app.post("/api/reports/ingest", dependencies=[Depends(auth)])
def ingest_report(payload: dict):
    """Store a report produced outside the backend (the frontend integration smoke test)."""
    status = str(payload.get("status", "ERROR")).upper()
    if status not in test_reports.STATUSES:
        raise HTTPException(422, "status must be PASS, FAIL, HOLD, ERROR or SKIPPED")
    run = test_reports.start(str(payload.get("category", "frontend_integration"))[:60], str(payload.get("name", "Frontend integration test"))[:200],
                             endpoint=str(payload.get("endpoint", "browser"))[:200], provider=payload.get("provider"), expected=payload.get("expected"))
    for st in (payload.get("steps") or [])[:200]:
        run.step(str(st.get("name", "step"))[:200], str(st.get("status", "completed"))[:20], str(st.get("detail", ""))[:500])
    run.finish(status, summary=str(payload.get("summary", ""))[:500] or status, acceptance=payload.get("acceptance") or [],
               execution_status="error" if status == "ERROR" else "completed")
    return {"report_id": run.id}
