"""MOCKED DetectifAI for unit tests — never a real provider response.

Each fake "person" speaks a different tone; the fake speaker service stores which person was enrolled under each
speaker_id and answers verify calls by comparing the person in the submitted audio with the enrolled one. This
lets the tests prove the plumbing (right speaker_id sent, right audio sent, response parsed, no stale results)
without spending credits. Real behaviour is checked separately in tests/test_detectifai_live.py."""
from __future__ import annotations

import io
import math
import struct
import wave

from app.detectify_provider import ProviderError, normalize_detection
from app.schemas import ProviderResult, ProviderStatus

PEOPLE = {"A": 180.0, "B": 260.0, "C": 340.0}  # fundamental frequency per fake person


def voice_wav(person: str, seconds: float, rate: int = 16000, silent: bool = False) -> bytes:
    """Speech-like signal: 0.4 s tone bursts separated by 0.1 s pauses (or pure silence)."""
    f = PEOPLE[person]
    frames = bytearray()
    for i in range(int(seconds * rate)):
        t = i / rate
        on = (t % 0.5) < 0.4 and not silent
        v = 0.35 * math.sin(2 * math.pi * f * t) if on else 0.0
        frames += struct.pack("<h", int(v * 32767))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))
    return buf.getvalue()


def person_in(data: bytes) -> str | None:
    """Recover the fake person from the tone (zero-crossing rate)."""
    with wave.open(io.BytesIO(data)) as w:
        raw = w.readframes(w.getnframes())
        rate = w.getframerate()
    samples = struct.unpack(f"<{len(raw) // 2}h", raw)
    voiced = [s for s in samples if abs(s) > 200]
    if len(voiced) < rate:  # less than ~1 s of voiced audio
        return None
    crossings = sum(1 for a, b in zip(voiced, voiced[1:]) if (a < 0) != (b < 0))
    freq = crossings / 2 / (len(voiced) / rate)
    return min(PEOPLE, key=lambda p: abs(PEOPLE[p] - freq))


class FakeSpeakerService:
    """Labelled MOCK of the three DetectifAI speaker endpoints used by GhostKey."""

    def __init__(self, unavailable: bool = False):
        self.enrolled: dict[str, list[str]] = {}
        self.verify_calls: list[dict] = []
        self.deleted: list[str] = []
        self.unavailable = unavailable

    def enroll_speaker(self, data, speaker_id, name, filename="e.wav", content_type="audio/wav"):
        who = person_in(data)
        if who is None:
            raise ProviderError("FAILED", "insufficient_speech", "MOCK: not enough speech to enroll")
        self.enrolled.setdefault(speaker_id, []).append(who)
        return {"operation_id": f"op_mock_enroll_{len(self.enrolled)}", "request_id": "req_mock", "speaker": {"speaker_id": speaker_id, "samples": len(self.enrolled[speaker_id])},
                "quality": {"speech_seconds": 15.0}}

    def delete_speaker(self, speaker_id):
        self.deleted.append(speaker_id)
        self.enrolled.pop(speaker_id, None)
        return {}

    def speaker_verification(self, data, speaker_id, filename="a.wav", content_type="audio/wav", detect_deepfake=True):
        self.verify_calls.append({"speaker_id": speaker_id, "person": person_in(data), "bytes": len(data)})
        if self.unavailable:
            return ProviderResult(capability="speaker_verification", status=ProviderStatus.UNAVAILABLE, error="network_error: MOCK provider down"), None
        who = person_in(data)
        if who is None:
            return ProviderResult(capability="speaker_verification", status=ProviderStatus.FAILED,
                                  error="insufficient_speech: MOCK needs at least 2 seconds of detected speech"), None
        if speaker_id not in self.enrolled:
            return ProviderResult(capability="speaker_verification", status=ProviderStatus.FAILED, error="speaker_not_found: MOCK"), None
        same = who in self.enrolled[speaker_id]
        sim = 0.81 if same else 0.12
        spk = ProviderResult(capability="speaker_verification", status=ProviderStatus.COMPLETED, classification="match" if same else "no_match",
                             score=sim, threshold=0.53, score_semantics="MOCK similarity", raw_result_reference="op_mock_verify",
                             details={"speaker_id": speaker_id, "request_id": "req_mock_verify", "model": {"name": "MOCK"}})
        df = normalize_detection({"verdict": "real", "score": 0.02, "threshold": 0.62, "segments": []}, "op_mock_df") if detect_deepfake else None
        return spk, df
