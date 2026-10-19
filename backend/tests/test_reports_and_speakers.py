"""Unit tests for the test-report system and the speaker enrollment/verification pipeline.
DetectifAI is MOCKED here (tests/speaker_fakes.py) — these prove the plumbing, not the model."""
import json
import os

import pytest
from fastapi.testclient import TestClient

import tempfile  # noqa: E402
os.environ.setdefault("GHOSTKEY_DB", "sqlite:///" + os.path.join(tempfile.gettempdir(), "ghostkey_test.db").replace("\\", "/"))
os.environ.setdefault("GHOSTKEY_API_TOKEN", "test-token")

from app import main  # noqa: E402
from app import report_service  # noqa: E402
from app.db import init_db  # noqa: E402
from app.detectify_provider import normalize_detection  # noqa: E402
from tests.speaker_fakes import FakeSpeakerService, voice_wav  # noqa: E402

init_db()
H = {"X-GhostKey-Token": os.environ["GHOSTKEY_API_TOKEN"]}


@pytest.fixture
def fake(monkeypatch):
    f = FakeSpeakerService()
    for name in ("enroll_speaker", "delete_speaker", "speaker_verification"):
        monkeypatch.setattr(main.provider, name, getattr(f, name))
    return f


@pytest.fixture
def client():
    with TestClient(main.app) as c:
        yield c


def _person(c, name, uc="banking"):
    return c.post("/api/identities", headers=H, data={"name": name, "use_case": uc}).json()["id"]


def _enroll(c, pid, who, seconds=12):
    r = c.post(f"/api/identities/{pid}/voice", headers=H, files={"audio": ("enroll.wav", voice_wav(who, seconds), "audio/wav")})
    assert r.status_code == 200, r.text
    return r.json()


def _verify(c, pid, who, seconds=6, **form):
    return c.post("/api/speakers/verify", headers=H, data={"identity_id": pid, **form}, files={"audio": ("v.wav", voice_wav(who, seconds), "audio/wav")})


def _report(c, rid):
    r = c.get(f"/api/reports/{rid}", headers=H)
    assert r.status_code == 200
    return r.json()


# ---------- speaker verification matrix (mocked provider) ----------
def test_1_enroll_a_verify_a_matches(fake, client):
    a = _person(client, "Matrix A1")
    _enroll(client, a, "A")
    body = _verify(client, a, "A").json()
    assert body["verification_outcome"] == "MATCH" and body["test_status"] == "PASS"
    assert fake.verify_calls[-1]["speaker_id"] == body["identity"]["speaker_id"] == a  # the selected person's stored id reached the provider
    rep = _report(client, body["report_id"])
    assert rep["status"] == "PASS" and rep["evidence"]["speaker_result"]["speaker_id_sent"] == a


def test_2_enroll_a_verify_b_is_rejected(fake, client):
    a = _person(client, "Matrix A2")
    _enroll(client, a, "A")
    body = _verify(client, a, "B").json()
    assert body["verification_outcome"] == "NO_MATCH" and body["test_status"] == "FAIL"
    rep = _report(client, body["report_id"])
    assert rep["execution_status"] == "completed" and rep["status"] == "FAIL"  # executed fine, identity rejected
    assert fake.verify_calls[-1]["person"] == "B"  # the submitted recording (not the enrollment) was sent


def test_3_enroll_b_verify_a_is_rejected(fake, client):
    b = _person(client, "Matrix B3")
    _enroll(client, b, "B")
    assert _verify(client, b, "A").json()["verification_outcome"] == "NO_MATCH"


def test_4_unenrolled_speaker_is_not_verified(fake, client):
    p = _person(client, "Matrix nobody")
    body = _verify(client, p, "A").json()
    assert body["status"] == "NOT_ENROLLED" and not fake.verify_calls
    assert _report(client, body["report_id"])["status"] == "SKIPPED"


def test_5_corrupted_audio(fake, client):
    a = _person(client, "Matrix A5")
    _enroll(client, a, "A")
    r = client.post("/api/speakers/verify", headers=H, data={"identity_id": a}, files={"audio": ("broken.wav", b"RIFF\x00\x00garbage", "audio/wav")})
    assert r.status_code == 422 and r.json()["report_id"]
    assert _report(client, r.json()["report_id"])["status"] == "ERROR"


def test_6_unsupported_format(fake, client):
    a = _person(client, "Matrix A6")
    _enroll(client, a, "A")
    r = client.post("/api/speakers/verify", headers=H, data={"identity_id": a}, files={"audio": ("notes.txt", b"hello", "text/plain")})
    assert r.status_code == 415 and _report(client, r.json()["report_id"])["diagnostics"]["failure_stage"] == "validate audio"


def test_7_silent_audio_is_hold_not_pass(fake, client):
    a = _person(client, "Matrix A7")
    _enroll(client, a, "A")
    r = client.post("/api/speakers/verify", headers=H, data={"identity_id": a}, files={"audio": ("quiet.wav", voice_wav("A", 6, silent=True), "audio/wav")})
    body = r.json()
    assert body["verification_outcome"] == "NOT_VERIFIED" and body["test_status"] == "HOLD"
    assert _report(client, body["report_id"])["diagnostics"]["hypotheses"]


def test_8_near_threshold_similarity_is_inconclusive(monkeypatch, client):
    from app.schemas import ProviderResult, ProviderStatus
    f = FakeSpeakerService()
    monkeypatch.setattr(main.provider, "enroll_speaker", f.enroll_speaker)
    monkeypatch.setattr(main.provider, "delete_speaker", f.delete_speaker)
    a = _person(client, "Matrix noisy")
    _enroll(client, a, "A")
    monkeypatch.setattr(main.provider, "speaker_verification", lambda *a_, **k: (ProviderResult(
        capability="speaker_verification", status=ProviderStatus.COMPLETED, classification="match", score=0.55, threshold=0.53, details={"speaker_id": a}), None))
    body = _verify(client, a, "A").json()
    assert body["verification_outcome"] == "INCONCLUSIVE" and body["test_status"] == "HOLD"


def test_9_provider_unavailable_is_error(monkeypatch, client):
    f = FakeSpeakerService(unavailable=True)
    for name in ("enroll_speaker", "delete_speaker", "speaker_verification"):
        monkeypatch.setattr(main.provider, name, getattr(f, name))
    a = _person(client, "Matrix down")
    _enroll(client, a, "A")
    body = _verify(client, a, "A").json()
    assert body["test_status"] == "ERROR"
    rep = _report(client, body["report_id"])
    assert rep["execution_status"] == "error" and rep["diagnostics"]["retry_eligible"] is True


def test_10_unknown_speaker_id(fake, client):
    r = _verify(client, "id_does_not_exist", "A")
    assert r.status_code == 404
    assert _report(client, r.json()["detail"]["report_id"])["status"] == "SKIPPED"


def test_11_consecutive_attempts_are_independent(fake, client):
    a = _person(client, "Matrix A11")
    _enroll(client, a, "A")
    r1, r2 = _verify(client, a, "A").json(), _verify(client, a, "B").json()
    assert (r1["verification_outcome"], r2["verification_outcome"]) == ("MATCH", "NO_MATCH")
    assert r1["attempt_id"] != r2["attempt_id"] and r1["report_id"] != r2["report_id"]
    assert r1["submitted_audio_sha256"] != r2["submitted_audio_sha256"]


def test_12_two_users_do_not_leak(fake, client):
    a, b = _person(client, "Leak A"), _person(client, "Leak B")
    _enroll(client, a, "A")
    _enroll(client, b, "B")
    assert _verify(client, a, "A").json()["verification_outcome"] == "MATCH"
    assert _verify(client, b, "B").json()["verification_outcome"] == "MATCH"
    assert _verify(client, a, "B").json()["verification_outcome"] == "NO_MATCH"
    assert {c["speaker_id"] for c in fake.verify_calls[-3:]} == {a, b}


def test_expected_label_turns_a_correct_rejection_into_pass(fake, client):
    a = _person(client, "Matrix labelled")
    _enroll(client, a, "A")
    body = _verify(client, a, "B", expected="different_person").json()
    assert body["verification_outcome"] == "NO_MATCH" and body["test_status"] == "PASS"
    assert _report(client, body["report_id"])["assessment"]["status_basis"] == "expected_vs_actual"


def test_reenrolling_replaces_the_voiceprint_instead_of_blending(fake, client):
    a = _person(client, "Blend check")
    _enroll(client, a, "A")
    _enroll(client, a, "B")  # someone re-enrolls this person with a different voice
    assert fake.deleted == [a] and fake.enrolled[a] == ["B"]  # old sample removed, not mixed in
    assert _verify(client, a, "A").json()["verification_outcome"] == "NO_MATCH"


def test_failed_enrollment_is_not_stored_as_success(fake, client):
    a = _person(client, "Bad enroll")
    r = client.post(f"/api/identities/{a}/voice", headers=H, files={"audio": ("e.wav", voice_wav("A", 12, silent=True), "audio/wav")})
    assert r.status_code == 422
    ident = next(i for i in client.get("/api/identities", headers=H).json() if i["id"] == a)
    assert ident["speaker_enrolled"] is False
    assert _report(client, r.json()["report_id"])["status"] == "FAIL"


# ---------- root-cause regression: the final decision must follow the speaker check ----------
def _judge(client, monkeypatch, fake, who_enrolled, who_speaks, context="F01", uc="family"):
    from app import examples as ex
    monkeypatch.setattr(ex.provider, "speaker_verification", fake.speaker_verification)
    monkeypatch.setattr(ex.provider, "audio_authenticity", lambda *a, **k: normalize_detection({"verdict": "real", "score": 0.02, "threshold": 0.62, "segments": []}, "op"))
    p = _person(client, f"Judge {who_enrolled}", uc)
    _enroll(client, p, who_enrolled)
    r = client.post(f"/api/test/{uc}", headers=H, data={"context_id": context, "person_identity_id": p, "speaker_identity_id": p},
                    files={"audio": ("me.wav", voice_wav(who_speaks, 6), "audio/wav")})
    assert r.status_code == 200, r.text
    return r.json()


def test_different_voice_no_longer_gets_the_same_verified_result(monkeypatch, fake, client):
    same = _judge(client, monkeypatch, fake, "A", "A")
    other = _judge(client, monkeypatch, fake, "A", "B")
    assert same["decision"]["outcome"] == "VERIFIED_AND_AUTHORIZED"  # F01: independent verification passed + voice matches
    # independent verification passed in F01, so the conflict goes to a reviewer — but it is never VERIFIED again
    assert other["decision"]["outcome"] == "ESCALATED_FOR_REVIEW" and other["decision"]["headline"].startswith("Speaker mismatch detected")
    no_auth = _judge(client, monkeypatch, fake, "A", "B", context="F02")  # F02: independent verification failed
    assert no_auth["decision"]["outcome"] == "HOLD_FOR_VERIFICATION" and no_auth["decision"]["headline"].startswith("Speaker mismatch")


def test_failed_speaker_check_holds_instead_of_authorizing(monkeypatch, fake, client):
    from app import examples as ex
    monkeypatch.setattr(ex.provider, "speaker_verification", fake.speaker_verification)
    monkeypatch.setattr(ex.provider, "audio_authenticity", lambda *a, **k: normalize_detection({"verdict": "real", "score": 0.02, "threshold": 0.62, "segments": []}, "op"))
    p = _person(client, "Judge quiet", "family")
    _enroll(client, p, "A")
    rec = client.post("/api/test/family", headers=H, data={"context_id": "F01", "person_identity_id": p, "speaker_identity_id": p},
                      files={"audio": ("me.wav", voice_wav("A", 6, silent=True), "audio/wav")}).json()
    assert rec["decision"]["outcome"] == "HOLD_FOR_VERIFICATION"


def test_banking_balance_enquiry_with_wrong_voice_is_not_authorized(monkeypatch, fake, client):
    rec = _judge(client, monkeypatch, fake, "A", "C", context="B01", uc="banking")
    assert rec["decision"]["outcome"] == "DENIED" and rec["decision"]["headline"] == "Speaker mismatch detected."


# ---------- reporting system ----------
def test_every_investigation_has_a_linked_persistent_report(client):
    rec = client.post("/api/scenarios/A/run", headers=H).json()
    rep = _report(client, rec["report_id"])
    assert rep["ids"]["case_id"] == rec["case_id"] and rep["status"] in ("PASS", "FAIL")
    assert rep["assessment"]["status_basis"] == "expected_vs_actual" and rep["status"] == "PASS"  # scenario A reaches its expected outcome
    assert rep["execution"]["agents"] and rep["evidence"]["policy"]["outcome"] == rec["decision"]["outcome"]
    stored = json.loads(main.SessionLocal().get(main.Investigation, rec["case_id"]).record)
    assert stored["report_id"] == rec["report_id"]


def test_hold_and_error_outcomes_are_persisted(client):
    hold = _report(client, client.post("/api/scenarios/E/run", headers=H).json()["report_id"])
    assert hold["verification_outcome"] == "HOLD_FOR_VERIFICATION"
    err = client.post("/api/audio/analyze", headers=H, files={"audio": ("bad.txt", b"x", "text/plain")}).json()
    assert _report(client, err["report_id"])["status"] == "ERROR"


def test_reports_survive_restart_and_export_matches(client):
    rid = client.post("/api/reports/ingest", headers=H, json={"name": "restart check", "status": "PASS", "summary": "ok"}).json()["report_id"]
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    fresh = sessionmaker(bind=create_engine(os.environ["GHOSTKEY_DB"]))()  # a new engine = a new process's view of the database
    from app.db import TestReport
    assert fresh.get(TestReport, rid).status == "PASS"
    exported = client.get(f"/api/reports/{rid}/export", headers=H)
    assert "attachment" in exported.headers["content-disposition"] and exported.json() == _report(client, rid)


def test_interrupted_running_report_is_marked_not_lost(client):
    run = report_service.start("speaker_verification", "interrupted run")
    run.step("DetectifAI POST /v1/speakers/verify", "running", "process killed here")
    with main.SessionLocal() as db:
        row = db.get(report_service.TestReport, run.id)
        row.created_at -= 3600
        db.commit()
    assert report_service.mark_interrupted() >= 1
    rep = _report(client, run.id)
    assert rep["status"] == "ERROR" and rep["execution_status"] == "incomplete"


def test_secrets_never_appear_in_reports(monkeypatch, client):
    monkeypatch.setenv("DETECTIF_API_KEY", "dtf_live_SUPERSECRETKEY123456")
    run = report_service.start("connectivity", "secret check")
    run.step("call", "failed", "Authorization: Bearer dtf_live_SUPERSECRETKEY123456 rejected", api_key="dtf_live_SUPERSECRETKEY123456")
    run.error(RuntimeError("bad key dtf_live_SUPERSECRETKEY123456"), "call")
    text = client.get(f"/api/reports/{run.id}/export", headers=H).text
    assert "SUPERSECRETKEY" not in text and "[redacted]" in text


def test_missing_optional_fields_do_not_crash(client):
    rid = client.post("/api/reports/ingest", headers=H, json={"status": "SKIPPED"}).json()["report_id"]
    assert _report(client, rid)["status"] == "SKIPPED"
    assert client.post("/api/reports/ingest", headers=H, json={"status": "MAYBE"}).status_code == 422
    listing = client.get("/api/reports?q=" + rid, headers=H).json()
    assert listing["total"] == 1 and listing["items"][0]["report_id"] == rid
    assert client.get("/api/reports/stats", headers=H).json()["total"] >= 1


def test_report_filters(client):
    client.post("/api/reports/ingest", headers=H, json={"status": "FAIL", "category": "frontend_integration", "name": "filter check"})
    fails = client.get("/api/reports?status=FAIL&category=frontend_integration", headers=H).json()["items"]
    assert fails and all(r["status"] == "FAIL" and r["category"] == "frontend_integration" for r in fails)


# ---------- forgiving configuration (values pasted into hosting dashboards) ----------
def test_config_accepts_messy_dashboard_values(monkeypatch):
    from app import config
    for n in config.DETECTIF_KEY_NAMES:
        monkeypatch.delenv(n, raising=False)
    monkeypatch.setenv("DETECTIFAI_KEY", '  "dtf_abc123xyz"\n')
    assert config.detectif_key() == ("dtf_abc123xyz", "DETECTIFAI_KEY")
    monkeypatch.delenv("DETECTIFAI_KEY")
    monkeypatch.setenv("MY_DETECTIF_SECRET_KEY", "dtf_other_value")  # any name with DETECTIF + KEY
    assert config.detectif_key()[0] == "dtf_other_value"
    monkeypatch.setenv("GHOSTKEY_MAX_AUDIO_MB", "25MB")
    assert config.env_float("GHOSTKEY_MAX_AUDIO_MB", 1) == 25
    monkeypatch.setenv("GHOSTKEY_PUBLIC", " TRUE ")
    assert config.env_bool("GHOSTKEY_PUBLIC", False) is True
    monkeypatch.setenv("GHOSTKEY_PUBLIC", "maybe")
    assert config.env_bool("GHOSTKEY_PUBLIC", False) is False
    monkeypatch.setenv("DETECTIFAI_BASE_URL", '"platform.detectif.ai/v1/"')
    assert config.detectif_base_url() == "https://platform.detectif.ai"
