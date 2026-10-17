"""REAL DetectifAI integration test — sends real requests and spends credits (~6 checks ≈ 300 credits).

Skipped unless GHOSTKEY_LIVE_TESTS=1 and a DetectifAI key is configured:

    GHOSTKEY_LIVE_TESTS=1 .venv/Scripts/python -m pytest -q tests/test_detectifai_live.py -s

Audio: two different real callers from MINDS-14 (PolyAI, CC BY 4.0) shipped in examples/family. Person A is
enrolled from one part of their call and verified with a different part of the same call; person B is a
different caller. Speakers created here are deleted at the end."""
import io
import os
import wave

import pytest
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
LIVE = os.getenv("GHOSTKEY_LIVE_TESTS") == "1" and bool(os.getenv("DETECTIF_API_KEY") or os.getenv("DETECTIFAI_API_KEY"))
pytestmark = pytest.mark.skipif(not LIVE, reason="real DetectifAI test: set GHOSTKEY_LIVE_TESTS=1 (spends credits)")

EX = os.path.join(os.path.dirname(os.path.dirname(__file__)), "examples", "family")


def cut(path: str, start: float, seconds: float) -> bytes:
    with wave.open(path) as w:
        p = w.getparams()
        w.setpos(int(start * p.framerate))
        frames = w.readframes(int(seconds * p.framerate))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as o:
        o.setparams(p)
        o.writeframes(frames)
    return buf.getvalue()


def test_real_speaker_matrix():
    from fastapi.testclient import TestClient
    from app import main
    H = {"X-GhostKey-Token": os.getenv("GHOSTKEY_API_TOKEN", "test-token")}
    results = {}
    with TestClient(main.app) as c:
        a = c.post("/api/identities", headers=H, data={"name": "LIVE TEST caller A (MINDS-14)", "use_case": "banking"}).json()["id"]
        try:
            enroll = c.post(f"/api/identities/{a}/voice", headers=H, files={"audio": ("a-enroll.wav", cut(f"{EX}/F01/call.wav", 0.5, 12.0), "audio/wav")})
            assert enroll.status_code == 200, enroll.text
            results["enroll"] = enroll.json()["report_id"]

            same = c.post("/api/speakers/verify", headers=H, data={"identity_id": a, "expected": "same_person"},
                          files={"audio": ("a-other-part.wav", cut(f"{EX}/F01/call.wav", 13.0, 8.0), "audio/wav")}).json()
            other = c.post("/api/speakers/verify", headers=H, data={"identity_id": a, "expected": "different_person"},
                           files={"audio": ("b.wav", cut(f"{EX}/F02/call.wav", 1.0, 8.0), "audio/wav")}).json()
            silent = c.post("/api/speakers/verify", headers=H, data={"identity_id": a},
                            files={"audio": ("silence.wav", b"RIFF" + cut(f"{EX}/F01/call.wav", 0, 0.01)[4:44] + b"\x00\x00" * 16000 * 5, "audio/wav")})
            for k, r in (("same", same), ("other", other)):
                rep = c.get(f"/api/reports/{r['report_id']}", headers=H).json()
                print(f"\n{k}: decision={r['speaker_result']['classification']} similarity={r['speaker_result']['score']} "
                      f"threshold={r['speaker_result']['threshold']} outcome={r['verification_outcome']} report={rep['report_id']} status={rep['status']}")
                assert rep["evidence"]["speaker_result"]["speaker_id_sent"] == a
            print(f"silent: status={silent.status_code} {str(silent.json())[:200]}")
            # acceptance: DetectifAI distinguishes the two real callers and both reports are persisted
            assert same["verification_outcome"] == "MATCH", same
            assert other["verification_outcome"] == "NO_MATCH", other
            assert same["speaker_result"]["score"] > other["speaker_result"]["score"]
        finally:
            c.delete(f"/api/identities/{a}", headers=H)  # also deletes the DetectifAI voiceprint
