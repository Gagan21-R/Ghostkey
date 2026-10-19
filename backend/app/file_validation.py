"""Upload validation before anything reaches DetectifAI or the face model.

Limits follow DetectifAI's docs (https://platform.detectif.ai/docs/audio-and-limits/): WAV, MP3, FLAC,
OGG/Opus, WebM, M4A/AAC, AIFF; up to 100 MB; deepfake check > 4 s and <= 120 s. GhostKey caps uploads at
GHOSTKEY_MAX_AUDIO_MB (default 25) to keep the demo fast. Uploaded files are processed in memory only and
never written to disk.
"""
from __future__ import annotations

import io
import math
import os
import wave

AUDIO_EXT = {".wav", ".mp3", ".flac", ".ogg", ".opus", ".oga", ".webm", ".m4a", ".aac", ".aiff", ".aif", ".mp4", ".3gp"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
from .config import env_float  # noqa: E402

MAX_AUDIO_MB = env_float("GHOSTKEY_MAX_AUDIO_MB", 25)
MAX_IMAGE_MB = env_float("GHOSTKEY_MAX_IMAGE_MB", 8)
MIN_DEEPFAKE_SECONDS, MAX_DEEPFAKE_SECONDS = 4.0, 120.0


class UploadError(ValueError):
    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def _ext(filename: str) -> str:
    return os.path.splitext(filename or "")[1].lower()


def wav_duration(data: bytes) -> float | None:
    try:
        with wave.open(io.BytesIO(data)) as w:
            return w.getnframes() / float(w.getframerate())
    except (wave.Error, EOFError, ZeroDivisionError):
        return None


def provider_file(filename: str, content_type: str | None) -> tuple[str, str]:
    """MP4/3GP audio (e.g. WhatsApp "Audio" downloads) is AAC in an MP4 container — DetectifAI's M4A/AAC."""
    base, ext = os.path.splitext(filename or "audio")
    if ext.lower() in (".mp4", ".3gp"):
        return base + ".m4a", "audio/mp4"
    return filename, content_type or "application/octet-stream"


def loop_wav(data: bytes, min_seconds: float = 16.0, max_seconds: float = 60.0) -> tuple[bytes, float]:
    """Repeat a short WAV until it reaches `min_seconds` (capped at `max_seconds`). Returns (wav, new duration)."""
    with wave.open(io.BytesIO(data)) as w:
        params, frames = w.getparams(), w.readframes(w.getnframes())
    rate = params.framerate
    seconds = len(frames) / (params.sampwidth * params.nchannels) / rate
    reps = max(1, math.ceil(min_seconds / max(seconds, 0.1)))
    out = (frames * reps)[: int(max_seconds * rate) * params.sampwidth * params.nchannels]
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setparams(params)
        w.writeframes(out)
    return buf.getvalue(), len(out) / (params.sampwidth * params.nchannels) / rate


def wav_speech_seconds(data: bytes) -> float | None:
    """Energy-based estimate of seconds of speech in a 16-bit WAV (20 ms frames well above the noise floor).
    A pre-check only — DetectifAI measures speech itself."""
    try:
        import numpy as np
        with wave.open(io.BytesIO(data)) as w:
            if w.getsampwidth() != 2:
                return None
            rate, ch = w.getframerate(), w.getnchannels()
            x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
    except Exception:
        return None
    if ch > 1:
        x = x[: len(x) // ch * ch].reshape(-1, ch).mean(axis=1)
    n = max(1, int(rate * 0.02))
    frames = x[: len(x) // n * n].reshape(-1, n)
    if not len(frames):
        return 0.0
    rms = np.sqrt((frames ** 2).mean(axis=1))
    thr = max(0.01, float(np.percentile(rms, 10)) * 4)
    return float((rms > thr).sum() * 0.02)


def validate_audio(filename: str, content_type: str | None, data: bytes, *, for_deepfake: bool = True) -> dict:
    ext = _ext(filename)
    if ext not in AUDIO_EXT and not (content_type or "").startswith("audio/"):
        raise UploadError("unsupported_format", f"'{ext or content_type}' is not a supported audio format (WAV, MP3, FLAC, OGG/Opus, WebM, M4A/AAC/MP4, AIFF).", 415)
    if not data:
        raise UploadError("empty_file", "The uploaded file is empty.")
    mb = len(data) / 1_000_000
    if mb > MAX_AUDIO_MB:
        raise UploadError("file_too_large", f"File is {mb:.1f} MB; the limit is {MAX_AUDIO_MB:.0f} MB.", 413)
    duration = wav_duration(data) if ext == ".wav" else None
    if ext == ".wav" and duration is None:
        raise UploadError("corrupt_audio", "The WAV file could not be read.")
    if duration is not None and for_deepfake and not (MIN_DEEPFAKE_SECONDS < duration <= MAX_DEEPFAKE_SECONDS):
        raise UploadError("bad_duration", f"Recording is {duration:.1f} s; DetectifAI's deepfake check needs more than 4 s and at most 120 s.")
    return {"filename": filename, "bytes": len(data), "duration_seconds": duration,
            "duration_checked": duration is not None, "note": None if duration is not None else "Duration is checked by DetectifAI for non-WAV formats."}


def validate_image(filename: str, content_type: str | None, data: bytes) -> None:
    ext = _ext(filename)
    if ext not in IMAGE_EXT and not (content_type or "").startswith("image/"):
        raise UploadError("unsupported_format", f"'{ext or content_type}' is not a supported image format (JPG, PNG, WebP, BMP).", 415)
    if not data:
        raise UploadError("empty_file", "The uploaded image is empty.")
    if len(data) / 1_000_000 > MAX_IMAGE_MB:
        raise UploadError("file_too_large", f"Image exceeds {MAX_IMAGE_MB:.0f} MB.", 413)
