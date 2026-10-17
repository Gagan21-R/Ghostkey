"""GhostKey tests — run without any live AI service: `.venv/Scripts/python -m pytest -q`."""
import os
import time

# test database outside OneDrive-synced folders (sync can corrupt a SQLite file mid-write)
import tempfile  # noqa: E402
TEST_DB = os.path.join(tempfile.gettempdir(), "ghostkey_test.db")
os.environ["GHOSTKEY_DB"] = "sqlite:///" + TEST_DB.replace("\\", "/")
os.environ["GHOSTKEY_API_TOKEN"] = "test-token"
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import adversarial_critic, audit_service, exam_identity_agent, orchestrator, policy_engine, scenarios, session_service  # noqa: E402
from app.db import init_db  # noqa: E402
from app.detectify_provider import DetectifyProvider, normalize_detection  # noqa: E402
from app.schemas import FindingStatus as F  # noqa: E402
from app.schemas import InvestigationRequest, PolicyOutcome, ProviderStatus, RequestedAction  # noqa: E402

init_db()


# ---------- provider ----------
def _provider(handler):
    return DetectifyProvider(api_key="k", base_url="https://example.test", transport=httpx.MockTransport(handler), max_retries=1)


def test_provider_normalizes_documented_response():
    body = {"operation_id": "op_1", "result": {"verdict": "fake", "score": 0.99, "threshold": 0.62, "decided_by": "main_model", "segments": [{"start": 0, "end": 4, "score": 0.98}]}}
    r = _provider(lambda req: httpx.Response(200, json=body)).audio_authenticity(b"x")
    assert r.status == ProviderStatus.COMPLETED and r.classification == "fake" and r.confidence is None and r.raw_result_reference == "op_1" and not r.simulated


def test_provider_not_sure_is_inconclusive():
    assert normalize_detection({"verdict": "not_sure", "score": 0.5}, "op").status == ProviderStatus.INCONCLUSIVE


def test_provider_unexpected_schema_fails_cleanly():
    assert normalize_detection({"label": "weird"}, "op").status == ProviderStatus.FAILED


def test_provider_errors_and_unavailable():
    r = _provider(lambda req: httpx.Response(401, json={"error": {"code": "invalid_api_key", "message": "bad"}})).audio_authenticity(b"x")
    assert r.status == ProviderStatus.FAILED and "invalid_api_key" in r.error
    calls = []

    def boom(req):
        calls.append(1)
        raise httpx.ConnectError("down")
    r = _provider(boom).audio_authenticity(b"x")
    assert r.status == ProviderStatus.UNAVAILABLE and len(calls) == 2  # bounded retries
    assert DetectifyProvider(api_key="").audio_authenticity(b"x").status == ProviderStatus.UNAVAILABLE
    assert DetectifyProvider(api_key="k").image_analysis().status == ProviderStatus.NOT_SUPPORTED


# ---------- policy engine (no AI needed) ----------
def _bank(action="pin_change", **kw):
    return InvestigationRequest(use_case="banking", actor_role=kw.pop("role", "customer"), requested_action=RequestedAction(type=action), **kw)


def test_voice_alone_never_authorizes_banking_change():
    req = _bank(audio_authenticity=scenarios.audio_fx("real", 0.01), speaker_verification=scenarios.speaker_fx("match", 0.9), speaker_reference_enrolled=True)
    findings = [m.analyze(req) for m in orchestrator.SPECIALISTS["banking"]]
    assert policy_engine.decide(req, findings, []).outcome == PolicyOutcome.HOLD_FOR_VERIFICATION


def test_unavailable_detector_is_not_success():
    req = _bank(audio_authenticity=DetectifyProvider(api_key="").audio_authenticity(b"x"))
    d = policy_engine.decide(req, [m.analyze(req) for m in orchestrator.SPECIALISTS["banking"]], [])
    assert d.outcome == PolicyOutcome.HOLD_FOR_VERIFICATION and any("R1" in r for r in d.rules_fired)


def test_unauthorized_role_denied_and_secrets_never_shared():
    assert policy_engine.decide(_bank(role="support_agent"), [], []).outcome == PolicyOutcome.DENIED
    fam = InvestigationRequest(use_case="family", actor_role="family_member", requested_action=RequestedAction(type="share_otp"), independent_verification={"status": "passed"})
    assert policy_engine.decide(fam, [], []).outcome == PolicyOutcome.DENIED


def test_full_auth_with_unresolved_disagreement_escalates():
    req = _bank(challenge_check={"valid": True, "reason": "x"}, approval_check={"valid": True, "reason": "y"})
    assert policy_engine.decide(req, [], ["conflict"]).outcome == PolicyOutcome.ESCALATED_FOR_REVIEW
    assert policy_engine.decide(req, [], []).outcome == PolicyOutcome.VERIFIED_AND_AUTHORIZED


def test_no_number_of_agent_votes_overrides_policy():
    req = _bank(audio_authenticity=scenarios.audio_fx("real", 0.01))
    votes = [m.analyze(req) for m in orchestrator.SPECIALISTS["banking"]] * 50
    assert policy_engine.decide(req, votes, []).outcome == PolicyOutcome.HOLD_FOR_VERIFICATION


# ---------- sessions ----------
def test_challenge_single_use_and_expiry():
    s = session_service.create_session("banking", "id", {"type": "pin_change"})
    c = session_service.issue_challenge(s["session_id"])
    assert session_service.verify_challenge(s["session_id"], c["challenge_id"], c["nonce_for_trusted_channel"])["valid"]
    assert session_service.verify_challenge(s["session_id"], c["challenge_id"], c["nonce_for_trusted_channel"])["reason"] == "replayed_challenge"
    c2 = session_service.issue_challenge(s["session_id"])
    assert session_service.verify_challenge(s["session_id"], c2["challenge_id"], c2["nonce_for_trusted_channel"], now=time.time() + 999)["reason"] == "expired_challenge"


def test_action_bound_approval_invalidated_on_change():
    s = session_service.create_session("banking", "id", {"type": "add_payee", "amount": 10})
    a = session_service.request_approval(s["session_id"], {"type": "add_payee", "amount": 10}, "phone")
    assert not session_service.decide_approval(a["approval_id"], True, "other-device")["ok"]
    session_service.decide_approval(a["approval_id"], True, "phone")
    assert session_service.check_approval(a["approval_id"], {"type": "add_payee", "amount": 10})["valid"]
    assert session_service.check_approval(a["approval_id"], {"type": "add_payee", "amount": 99999})["reason"] == "action_changed_after_approval"


# ---------- agents ----------
def test_exam_states():
    base = dict(use_case="exam", requested_action=RequestedAction(type="start_exam"), face_reference_enrolled=True)
    assert exam_identity_agent.analyze(InvestigationRequest(**base, face_frames=scenarios.frames_fx([0.6, 0.7, 0.65, 0.62]))).status == F.FACE_MATCH_SUPPORTED
    assert exam_identity_agent.analyze(InvestigationRequest(**base, face_frames=scenarios.frames_fx([0.1, 0.12, 0.08]))).status == F.FACE_MISMATCH_SUSPECTED
    assert exam_identity_agent.analyze(InvestigationRequest(**base, face_frames=scenarios.frames_fx([0.3, 0.3, 0.3], brightness=20))).status == F.LIVENESS_INCONCLUSIVE
    assert exam_identity_agent.analyze(InvestigationRequest(**base, face_frames=scenarios.frames_fx([0.6, 0.6, 0.6], faces=2))).status == F.MULTIPLE_FACES_DETECTED
    assert exam_identity_agent.analyze(InvestigationRequest(**{**base, "face_reference_enrolled": False}, face_frames=[])).status == F.REFERENCE_IMAGE_MISSING


def test_face_match_never_proves_liveness():
    req = InvestigationRequest(use_case="exam", actor_role="student", requested_action=RequestedAction(type="start_exam"), face_reference_enrolled=True,
                               face_frames=scenarios.frames_fx([0.6, 0.7, 0.65]))
    d = policy_engine.decide(req, [exam_identity_agent.analyze(req)], [])
    assert d.outcome == PolicyOutcome.VERIFIED_AND_AUTHORIZED
    assert any(r.name == "liveness_proven" and not r.satisfied for r in d.requirements)


def test_critic_forces_clone_revision():
    rec = scenarios.run("E")
    speaker = next(f for f in rec["findings"] if f["finding_type"] == "speaker_identity")
    assert speaker["status"] == F.SPEAKER_MATCH_NOT_SUFFICIENT.value and speaker["revision"] == 1
    assert rec["reconciliation"]["disagreements"] and rec["reconciliation"]["changed_after_challenge"]


@pytest.mark.parametrize("sid", list(scenarios.SCENARIOS))
def test_every_scenario_reaches_expected_outcome(sid):
    rec = scenarios.run(sid)
    assert rec["decision"]["outcome"] == rec["expected_outcome"]


def test_scenarios_are_not_all_the_same():
    assert len({scenarios.SCENARIOS[s]["expected"] for s in scenarios.SCENARIOS}) == 4


# ---------- audit & API ----------
def test_audit_chain_detects_tampering():
    audit_service.record("test.event", "x", {"a": 1})
    assert audit_service.verify_chain()["ok"]
    from app.db import AuditEvent, SessionLocal
    with SessionLocal() as db:
        row = db.query(AuditEvent).order_by(AuditEvent.seq.desc()).first()
        row.payload = {"a": 2}
        db.commit()
    assert not audit_service.verify_chain()["ok"]


def test_api_requires_token():
    from app.main import app
    with TestClient(app) as c:
        assert c.get("/api/health").status_code == 200
        assert c.get("/api/scenarios").status_code == 401
        assert c.get("/api/scenarios", headers={"X-GhostKey-Token": "test-token"}).status_code == 200


# ---------- added for the revised spec ----------
import io  # noqa: E402
import wave  # noqa: E402

from app import file_validation, insurance_claim_agent  # noqa: E402
from app.insurance_data import CLAIMS, POLICYHOLDERS  # noqa: E402

H = {"X-GhostKey-Token": "test-token"}


def _wav(seconds: float) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * int(16000 * seconds))
    return buf.getvalue()


def test_upload_validation_rejects_bad_files():
    with pytest.raises(file_validation.UploadError) as e:
        file_validation.validate_audio("notes.txt", "text/plain", b"hello")
    assert e.value.code == "unsupported_format"
    with pytest.raises(file_validation.UploadError) as e:
        file_validation.validate_audio("short.wav", "audio/wav", _wav(2))
    assert e.value.code == "bad_duration"
    with pytest.raises(file_validation.UploadError) as e:
        file_validation.validate_audio("big.wav", "audio/wav", b"0" * int((file_validation.MAX_AUDIO_MB + 1) * 1_000_000))
    assert e.value.code == "file_too_large"
    assert file_validation.validate_audio("ok.wav", "audio/wav", _wav(5))["duration_seconds"] == pytest.approx(5)
    with pytest.raises(file_validation.UploadError):
        file_validation.validate_image("x.gif.exe", "application/octet-stream", b"MZ")


def test_api_upload_errors_are_structured():
    from app.main import app
    with TestClient(app) as c:
        r = c.post("/api/audio/analyze", headers=H, files={"audio": ("bad.txt", b"hello", "text/plain")})
        assert r.status_code == 415 and r.json()["code"] == "unsupported_format"


def test_secrets_never_returned_to_browser():
    from app.main import app
    os.environ["DETECTIF_API_KEY"] = "dtf_live_SECRET_SHOULD_NOT_LEAK"
    from app.detectify_provider import provider
    provider.api_key = os.environ["DETECTIF_API_KEY"]
    with TestClient(app) as c:
        for path in ("/api/settings", "/api/provider/status"):
            body = c.get(path, headers=H).text
            assert "SECRET_SHOULD_NOT_LEAK" not in body and "test-token" not in body
    provider.api_key = ""


def test_simulated_results_never_labelled_live():
    rec = scenarios.run("A")
    for f in rec["findings"]:
        if f["finding_type"] in ("voice_authenticity", "speaker_identity"):
            assert f["evidence_source"] == "simulated_fixture"
            assert all("SIMULATED" in ref for ref in f["evidence_refs"])
    assert rec["simulated_inputs"] is True
    assert all("live DetectifAI" not in e["detail"] for e in rec["timeline"] if e["step"] == "provider")


def test_insurance_agent_flags_but_never_accuses():
    claim = CLAIMS["CLM-2026-1121"]
    req = InvestigationRequest(use_case="insurance", requested_action=RequestedAction(type=claim["requested_action"]), claim=claim, policyholder=POLICYHOLDERS["ph-fatima"])
    f = insurance_claim_agent.analyze(req)
    assert f.status == F.CLAIM_ANOMALIES_FOUND and any("duplicate" in o for o in f.observations)
    assert "not evidence of fraud" in " ".join(f.limitations)


def test_insurance_four_outcomes_and_voice_alone_insufficient():
    outcomes = {sid: scenarios.run(sid)["decision"]["outcome"] for sid in ("L", "M", "N", "O")}
    assert outcomes == {"L": "VERIFIED_AND_AUTHORIZED", "M": "HOLD_FOR_VERIFICATION", "N": "HOLD_FOR_VERIFICATION", "O": "ESCALATED_FOR_REVIEW"}
    # payout change with a perfect-looking voice but no challenge/approval is still held
    claim = {**CLAIMS["CLM-2026-1042"], "requested_action": "change_payout_details"}
    req = InvestigationRequest(use_case="insurance", actor_role="policyholder", requested_action=RequestedAction(type="change_payout_details"), claim=claim,
                               policyholder=POLICYHOLDERS["ph-anita"], speaker_reference_enrolled=True,
                               audio_authenticity=scenarios.audio_fx("real", 0.01), speaker_verification=scenarios.speaker_fx("match", 0.95))
    findings = [m.analyze(req) for m in orchestrator.SPECIALISTS["insurance"]]
    assert policy_engine.decide(req, findings, []).outcome == PolicyOutcome.HOLD_FOR_VERIFICATION


def test_provider_failure_during_mandatory_voice_check_holds():
    claim = {**CLAIMS["CLM-2026-1042"], "requested_action": "change_payout_details"}
    req = InvestigationRequest(use_case="insurance", actor_role="policyholder", requested_action=RequestedAction(type="change_payout_details"), claim=claim,
                               policyholder=POLICYHOLDERS["ph-anita"], speaker_reference_enrolled=True,
                               audio_authenticity=DetectifyProvider(api_key="").audio_authenticity(b"x"),
                               challenge_check={"valid": True, "reason": "x"}, approval_check={"valid": True, "reason": "y"})
    findings = [m.analyze(req) for m in orchestrator.SPECIALISTS["insurance"]]
    d = policy_engine.decide(req, findings, [])
    assert d.outcome == PolicyOutcome.HOLD_FOR_VERIFICATION and any("R1" in r for r in d.rules_fired)


def test_provider_timeout_and_insufficient_credits():
    def slow(req):
        raise httpx.ReadTimeout("timed out")
    assert _provider(slow).audio_authenticity(b"x").status == ProviderStatus.UNAVAILABLE
    r = _provider(lambda req: httpx.Response(402, json={"error": {"code": "insufficient_credits", "message": "no credits"}})).audio_authenticity(b"x")
    assert r.status == ProviderStatus.FAILED and "insufficient_credits" in r.error and not r.simulated


def test_agent_crash_is_recorded_not_passed(monkeypatch):
    from app import contextual_risk_agent
    monkeypatch.setattr(contextual_risk_agent, "analyze", lambda req: (_ for _ in ()).throw(RuntimeError("boom")))
    rec = orchestrator.run(_bank(audio_authenticity=scenarios.audio_fx("real", 0.01)))
    crashed = [f for f in rec["findings"] if f["agent"] == "contextual_risk_agent"][0]
    assert crashed["execution_status"] == "failed" and crashed["status"] == "UNAVAILABLE"
    assert rec["decision"]["outcome"] == "HOLD_FOR_VERIFICATION"
    assert rec["correlation_id"].startswith("cor_") and all(f["correlation_id"] == rec["correlation_id"] for f in rec["findings"])


def test_case_deletion_and_auth_failure():
    from app.main import app
    with TestClient(app) as c:
        rec = c.post("/api/scenarios/B/run", headers=H).json()
        assert c.delete(f"/api/investigations/{rec['investigation_id']}", headers={"X-GhostKey-Token": "wrong"}).status_code == 401
        assert c.delete(f"/api/investigations/{rec['investigation_id']}", headers=H).json()["ok"]
        assert c.get(f"/api/investigations/{rec['investigation_id']}", headers=H).status_code == 404


def test_single_image_match_cannot_authorize_exam():
    req = InvestigationRequest(use_case="exam", actor_role="student", requested_action=RequestedAction(type="start_exam"), face_reference_enrolled=True,
                               face_frames=scenarios.frames_fx([0.7]))
    d = policy_engine.decide(req, [exam_identity_agent.analyze(req)], [])
    assert d.outcome == PolicyOutcome.HOLD_FOR_VERIFICATION


def test_action_hash_normalizes_numbers_but_detects_real_changes():
    a = {"type": "change_payout_details", "amount": 84000, "details": {"claim_id": "C1", "new_payout_account": "Axis 0099"}}
    assert session_service.action_hash(a) == session_service.action_hash({**a, "amount": 84000.0})
    assert session_service.action_hash(a) != session_service.action_hash({**a, "details": {"claim_id": "C1", "new_payout_account": "Unknown 7765"}})


# ---------- real-human example library ----------
from app import examples as example_lib  # noqa: E402


def test_at_least_ten_real_human_examples_per_use_case():
    assert len(example_lib.listing("exam")["examples"]) >= 10
    for uc in ("family", "insurance"):
        ex = example_lib.listing(uc)["examples"]
        assert sum(1 for e in ex if e["voice_truth"] == "human") >= 10
        assert all(os.path.exists(os.path.join(example_lib.EX_DIR, uc, e["audio"])) for e in ex)


@pytest.mark.parametrize("case", example_lib.listing("exam")["examples"], ids=lambda c: c["id"])
def test_exam_examples_match_ground_truth_with_real_face_model(case):
    rec = example_lib.run("exam", case["id"])
    face = next(f for f in rec["findings"] if f["finding_type"] == "exam_identity")
    assert face["status"] == case["expected_state"]
    assert face["evidence_source"] == "local_face_model"


def test_free_voice_example_run_never_pretends_to_have_checked():
    rec = example_lib.run("family", "F02", live=False)
    voice = next(f for f in rec["findings"] if f["finding_type"] == "voice_authenticity")
    assert voice["status"] == "UNAVAILABLE" and voice["evidence_source"] == "none"
    assert rec["example"]["live_voice_check"] is False
    assert rec["decision"]["outcome"] == "HOLD_FOR_VERIFICATION"


# ---------- judge test endpoint ----------
def test_judge_test_runs_uploaded_audio_through_pipeline(monkeypatch):
    from app import examples as ex
    from app.main import app
    calls = []

    def fake_detect(data, filename="a.wav", content_type="audio/wav"):
        calls.append(filename)
        return normalize_detection({"verdict": "fake", "score": 0.99, "threshold": 0.62, "segments": []}, "op_test")
    monkeypatch.setattr(ex.provider, "audio_authenticity", fake_detect)
    with TestClient(app) as c:
        r = c.post("/api/test/banking", headers=H, data={"context_id": "B06", "transcript": "please add the payee urgently"},
                   files={"audio": ("my-clone.wav", _wav(6), "audio/wav")})
        assert r.status_code == 200, r.text
        rec = r.json()
        assert calls == ["my-clone.wav"] and rec["example"]["judge_test"] is True
        voice = next(f for f in rec["findings"] if f["finding_type"] == "voice_authenticity")
        assert voice["status"] == "SYNTHETIC_INDICATORS" and voice["evidence_source"] == "live_provider"
        assert rec["decision"]["outcome"] == "ESCALATED_FOR_REVIEW"  # full auth but synthetic voice → human review
        assert c.post("/api/test/exam", headers=H, data={"context_id": "S01"}, files={"audio": ("a.wav", _wav(6), "audio/wav")}).status_code == 404
        assert c.post("/api/test/family", headers=H, data={"context_id": "F01"}, files={"audio": ("a.txt", b"hi", "text/plain")}).status_code == 415


def test_banking_examples_cover_all_outcomes():
    from app import examples as ex
    outs = {ex.run("banking", e["id"])["decision"]["outcome"] for e in ex.listing("banking")["examples"]}
    assert outs == {"VERIFIED_AND_AUTHORIZED", "HOLD_FOR_VERIFICATION", "DENIED"} or len(outs) >= 3


# ---------- quick enrollment, added people, downloads picker ----------
def test_short_enrollment_sample_is_looped_to_provider_minimum(monkeypatch):
    from tests.speaker_fakes import voice_wav
    from app import main
    sent = {}

    def fake_enroll(data, speaker_id, name, filename="e.wav", content_type="audio/wav"):
        sent["seconds"] = file_validation.wav_duration(data)
        return {"operation_id": "op_e", "speaker": {"speaker_id": speaker_id, "samples": 1}, "quality": {"speech_seconds": 15}}
    monkeypatch.setattr(main.provider, "enroll_speaker", fake_enroll)
    monkeypatch.setattr(main.provider, "delete_speaker", lambda sid: {})
    with TestClient(main.app) as c:
        pid = c.post("/api/identities", headers=H, data={"name": "Judge Quick", "use_case": "family"}).json()["id"]
        r = c.post(f"/api/identities/{pid}/voice", headers=H, files={"audio": ("me.wav", voice_wav("A", 4.5), "audio/wav")})
        assert r.status_code == 200, r.text
        body = r.json()
        assert 15 <= sent["seconds"] <= 60 and body["recorded_seconds"] == pytest.approx(4.5, abs=0.01) and body["looped_to_seconds"] >= 15 and body["note"]
        assert c.post(f"/api/identities/{pid}/voice", headers=H, files={"audio": ("me.wav", voice_wav("A", 1.5), "audio/wav")}).status_code == 422
        # a 20 s sample goes through untouched
        assert c.post(f"/api/identities/{pid}/voice", headers=H, files={"audio": ("me.wav", voice_wav("A", 20), "audio/wav")}).json()["looped_to_seconds"] is None
        # 10 s of silence (muted microphone) is refused before anything reaches DetectifAI, with a report
        r = c.post(f"/api/identities/{pid}/voice", headers=H, files={"audio": ("me.wav", _wav(10), "audio/wav")})
        assert r.status_code == 422 and r.json()["code"] == "insufficient_speech" and r.json()["report_id"]


def test_added_person_becomes_the_caller_and_can_be_deleted(monkeypatch):
    from app import examples as ex
    from app import main
    monkeypatch.setattr(ex.provider, "audio_authenticity", lambda *a, **k: normalize_detection({"verdict": "real", "score": 0.05, "threshold": 0.62, "segments": []}, "op_r"))
    deleted = []
    monkeypatch.setattr(main.provider, "delete_speaker", lambda sid: deleted.append(sid) or {})
    with TestClient(main.app) as c:
        pid = c.post("/api/identities", headers=H, data={"name": "Judge Priya", "use_case": "insurance"}).json()["id"]
        rec = c.post("/api/test/insurance", headers=H, data={"context_id": "I01", "person_identity_id": pid}, files={"audio": ("me.wav", _wav(6), "audio/wav")}).json()
        assert rec["example"]["person"] == "Judge Priya" and "Judge Priya" in rec["title"]
        assert c.delete(f"/api/identities/{pid}", headers=H).json()["ok"]
        assert all(i["id"] != pid for i in c.get("/api/identities", headers=H).json())
        assert c.delete("/api/identities/id-zira", headers=H).status_code == 400  # built-in people stay


def test_mp4_audio_is_accepted_and_sent_as_m4a():
    assert file_validation.validate_audio("WhatsApp Audio.mp4", "video/mp4", b"x")["duration_checked"] is False
    assert file_validation.provider_file("WhatsApp Audio.mp4", "video/mp4") == ("WhatsApp Audio.m4a", "audio/mp4")
    seen = {}

    def handler(req):
        seen["body"] = req.content
        return httpx.Response(200, json={"operation_id": "op", "result": {"verdict": "real", "score": 0.1, "threshold": 0.62}})
    _provider(handler).audio_authenticity(b"x", filename="clip.mp4", content_type="video/mp4")
    assert b'filename="clip.m4a"' in seen["body"] and b"audio/mp4" in seen["body"]


def test_downloads_picker_lists_newest_audio_only(tmp_path, monkeypatch):
    from app import main
    (tmp_path / "old.ogg").write_bytes(b"o")
    os.utime(tmp_path / "old.ogg", (time.time() - 86400, time.time() - 86400))
    (tmp_path / "new.mp4").write_bytes(b"n")
    (tmp_path / "notes.pdf").write_bytes(b"p")
    monkeypatch.setattr(main, "DOWNLOADS_DIR", str(tmp_path))
    monkeypatch.setattr(main, "LOCAL_DOWNLOADS", True)  # the public .env turns the picker off
    with TestClient(main.app) as c:
        files = c.get("/api/local/downloads", headers=H).json()["files"]
        assert [f["name"] for f in files] == ["new.mp4", "old.ogg"]
        assert c.get("/api/local/downloads/file", headers=H, params={"name": "new.mp4"}).content == b"n"
        assert c.get("/api/local/downloads/file", headers=H, params={"name": "notes.pdf"}).status_code == 404
        assert c.get("/api/local/downloads/file", headers=H, params={"name": "../secret.ogg"}).status_code == 404
