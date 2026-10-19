"""DetectifAI ("Detectify AI") provider.

Only capabilities confirmed in the public docs (https://platform.detectif.ai/docs/api/, OpenAPI at
https://platform.detectif.ai/v1/openapi.json) are implemented:
  - audio authenticity:   POST /v1/deepfake/detect      (multipart `file`, > 4 s and <= 120 s)
  - speaker verification: POST /v1/speakers/verify      (`file`, `speaker_id`, optional `detect_deepfake`)
  - speaker enrollment:   POST /v1/speakers/enroll      (`file`, `speaker_id`, `display_name`; 15–60 s)
  - health / credits:     GET  /v1/health, GET /v1/credits
Image analysis is NOT in the documented API, so it returns NOT_SUPPORTED.
"""
from __future__ import annotations

import os
import time
import uuid
from typing import Optional

import httpx

from . import config
from .file_validation import provider_file
from .schemas import ProviderResult, ProviderStatus

BASE_URL = config.detectif_base_url()
TIMEOUT = httpx.Timeout(45.0, connect=10.0)
RETRYABLE = {429, 500, 502, 503, 504}

DOC_LIMITATIONS = [
    "DetectifAI docs: results are signals, not proof; combine with other checks.",
    "DetectifAI docs: phone-quality audio and voice messages give less reliable results.",
    "DetectifAI docs: the AI-generated speech check is tuned for English.",
]
CAPABILITIES = {
    "audio_authenticity": "supported (POST /v1/deepfake/detect)",
    "speaker_verification": "supported (POST /v1/speakers/verify, requires an enrolled speaker)",
    "speaker_enrollment": "supported (POST /v1/speakers/enroll)",
    "image_analysis": "not in the documented API",
}


class DetectifyProvider:
    def __init__(self, api_key: Optional[str] = None, base_url: str = BASE_URL, transport: Optional[httpx.BaseTransport] = None, max_retries: int = 2):
        self.api_key = api_key if api_key is not None else config.detectif_key()[0]
        self.base_url = base_url
        self.max_retries = max_retries
        self._transport = transport

    # ---------- transport ----------
    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=TIMEOUT, transport=self._transport)

    def _request(self, method: str, path: str, *, files=None, data=None, auth: bool = True) -> dict:
        if auth and not self.api_key:
            raise ProviderError("UNAVAILABLE", "missing_api_key", "DetectifAI key is not configured: set DETECTIF_API_KEY in the server environment (backend/.env locally, Variables on Railway/Render)")
        headers = {"Authorization": f"Bearer {self.api_key}"} if auth else {}
        if method == "POST":
            headers["Idempotency-Key"] = str(uuid.uuid4())  # same key on retries → no double charge
        last: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                with self._client() as c:
                    r = c.request(method, path, headers=headers, files=files, data=data)
            except httpx.HTTPError as e:  # network / timeout
                last = ProviderError("UNAVAILABLE", "network_error", str(e))
                time.sleep(0.5 * (attempt + 1))
                continue
            body = _json(r)
            if r.status_code < 400:
                return body
            err = body.get("error", {}) if isinstance(body, dict) else {}
            last = ProviderError("FAILED" if r.status_code < 500 else "UNAVAILABLE", err.get("code", f"http_{r.status_code}"), err.get("message", r.text[:200]))
            if r.status_code in RETRYABLE and attempt < self.max_retries:
                time.sleep(min(float(r.headers.get("retry-after", 1) or 1), 4))
                continue
            break
        raise last  # type: ignore[misc]

    # ---------- capabilities ----------
    def health(self) -> dict:
        try:
            return {"reachable": True, **self._request("GET", "/v1/health", auth=False)}
        except ProviderError as e:
            return {"reachable": False, "error": e.message}

    def credits(self) -> dict:
        try:
            return self._request("GET", "/v1/credits")
        except ProviderError as e:
            return {"error": e.message, "code": e.code}

    def audio_authenticity(self, audio: bytes, filename: str = "audio.wav", content_type: str = "audio/wav") -> ProviderResult:
        try:
            name, ctype = provider_file(filename, content_type)
            body = self._request("POST", "/v1/deepfake/detect", files={"file": (name, audio, ctype)})
        except ProviderError as e:
            return _error_result("audio_authenticity", e)
        return normalize_detection(body.get("result", {}), body.get("operation_id"), body.get("request_id"), body.get("model"))

    def speaker_verification(self, audio: bytes, speaker_id: str, filename: str = "audio.wav", content_type: str = "audio/wav", detect_deepfake: bool = True) -> tuple[ProviderResult, Optional[ProviderResult]]:
        try:
            name, ctype = provider_file(filename, content_type)
            body = self._request("POST", "/v1/speakers/verify", files={"file": (name, audio, ctype)},
                                 data={"speaker_id": speaker_id, "detect_deepfake": "true" if detect_deepfake else "false"})
        except ProviderError as e:
            return _error_result("speaker_verification", e), None
        res = body.get("result", {})
        speaker = ProviderResult(
            capability="speaker_verification",
            status=ProviderStatus.COMPLETED,
            classification=res.get("decision"),
            score=res.get("similarity"),
            threshold=res.get("threshold"),
            score_semantics=res.get("similarity_semantics") or "cosine-style similarity, -1..1, not a percentage",
            evidence_summary=[f"decision={res.get('decision')} similarity={res.get('similarity')} threshold={res.get('threshold')}"],
            limitations=["A speaker match does not show the audio is human: a voice clone can match.", *DOC_LIMITATIONS[:1]],
            raw_result_reference=body.get("operation_id"),
            details={"duration_seconds": res.get("duration_seconds"), "speaker_id": speaker_id, "request_id": body.get("request_id"), "model": body.get("model")},
        )
        deepfake = None
        df = body.get("deepfake")
        if detect_deepfake and df:
            deepfake = _error_result("audio_authenticity", ProviderError("FAILED", df["error"].get("code", "error"), df["error"].get("message", ""))) if df.get("error") else normalize_detection(df, df.get("operation_id"), body.get("request_id"), df.get("model"))
        return speaker, deepfake

    def enroll_speaker(self, audio: bytes, speaker_id: str, display_name: str, filename: str = "enroll.wav", content_type: str = "audio/wav") -> dict:
        name, ctype = provider_file(filename, content_type)
        return self._request("POST", "/v1/speakers/enroll", files={"file": (name, audio, ctype)},
                             data={"speaker_id": speaker_id, "display_name": display_name})

    def delete_speaker(self, speaker_id: str) -> dict:
        return self._request("DELETE", f"/v1/speakers/{speaker_id}")

    def image_analysis(self, *_args, **_kwargs) -> ProviderResult:
        return ProviderResult(capability="image_analysis", status=ProviderStatus.NOT_SUPPORTED,
                              limitations=["Image analysis is not part of DetectifAI's documented API; GhostKey uses its own face model."])


class ProviderError(Exception):
    def __init__(self, status: str, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _json(r: httpx.Response) -> dict:
    try:
        return r.json()
    except ValueError:
        return {}


def _error_result(capability: str, e: ProviderError) -> ProviderResult:
    return ProviderResult(capability=capability, status=ProviderStatus(e.status), error=f"{e.code}: {e.message}",
                          limitations=["No provider result: this must not be read as a passed or failed check."])


def normalize_detection(res: dict, operation_id: Optional[str], request_id: Optional[str] = None, model: Optional[dict] = None) -> ProviderResult:
    """Maps DetectifAI's documented deepfake result onto the internal schema without reinterpreting it."""
    verdict = res.get("verdict")  # documented: real | fake | not_sure
    if verdict not in ("real", "fake", "not_sure"):
        return ProviderResult(capability="audio_authenticity", status=ProviderStatus.FAILED, error="unexpected response schema",
                              raw_result_reference=operation_id, details={"raw_keys": sorted(res.keys())})
    segments = res.get("segments") or []
    return ProviderResult(
        capability="audio_authenticity",
        status=ProviderStatus.INCONCLUSIVE if verdict == "not_sure" else ProviderStatus.COMPLETED,
        classification=verdict,
        score=res.get("score"),
        threshold=res.get("threshold"),
        score_semantics="0–1, higher = more likely AI-generated (vendor score, not a calibrated probability)",
        evidence_summary=[
            f"verdict={verdict} score={res.get('score')} threshold={res.get('threshold')} decided_by={res.get('decided_by')}",
            f"{len(segments)} segments, max segment score {max((s.get('score', 0) for s in segments), default=None)}",
        ],
        limitations=list(DOC_LIMITATIONS),
        raw_result_reference=operation_id,
        details={"request_id": request_id, "model": model, "decided_by": res.get("decided_by"), "route": res.get("route"), "language": res.get("language"),
                 "duration_seconds": res.get("duration_seconds"), "segments": segments},
    )


provider = DetectifyProvider()
