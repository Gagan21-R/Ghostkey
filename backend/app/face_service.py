"""Face verification with real models: OpenCV YuNet (detection) + SFace (128-d embeddings).
Models: https://github.com/opencv/opencv_zoo (Apache-2.0). Cosine threshold 0.363 is OpenCV's published value."""
from __future__ import annotations

import hashlib
import os
import time
from typing import Optional

import cv2
import numpy as np

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
DETECTOR = os.path.join(MODEL_DIR, "face_detection_yunet_2023mar.onnx")
RECOGNIZER = os.path.join(MODEL_DIR, "face_recognition_sface_2021dec.onnx")
THRESHOLD = 0.363
MODEL_INFO = {"name": "OpenCV YuNet 2023mar + SFace 2021dec", "threshold": THRESHOLD, "metric": "cosine"}

_rec = None


def available() -> bool:
    return os.path.exists(DETECTOR) and os.path.exists(RECOGNIZER)


def _recognizer():
    global _rec
    if _rec is None:
        _rec = cv2.FaceRecognizerSF.create(RECOGNIZER, "")
    return _rec


def _decode(img_bytes: bytes) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("not an image")
    h, w = img.shape[:2]
    if max(h, w) > 960:
        s = 960 / max(h, w)
        img = cv2.resize(img, (int(w * s), int(h * s)))
    return img


def _detect(img: np.ndarray):
    h, w = img.shape[:2]
    det = cv2.FaceDetectorYN.create(DETECTOR, "", (w, h), 0.8, 0.3, 5000)
    _, faces = det.detect(img)
    return [] if faces is None else list(faces)


def embed(img_bytes: bytes) -> dict:
    """For reference enrollment: exactly one face required. Returns the embedding only (no image kept)."""
    img = _decode(img_bytes)
    faces = _detect(img)
    if len(faces) != 1:
        return {"ok": False, "faces": len(faces), "reason": "exactly one face is required for a reference image"}
    rec = _recognizer()
    feat = rec.feature(rec.alignCrop(img, faces[0]))
    return {"ok": True, "faces": 1, "embedding": feat.flatten().tolist(), "detection_score": float(faces[0][-1])}


def analyze_frame(img_bytes: bytes, reference: Optional[list[float]], index: int) -> dict:
    img = _decode(img_bytes)
    faces = _detect(img)
    brightness = float(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).mean())
    best, score = None, None
    if reference is not None and faces:
        rec = _recognizer()
        ref = np.array(reference, dtype=np.float32).reshape(1, -1)
        sims = [float(rec.match(rec.feature(rec.alignCrop(img, f)), ref, cv2.FaceRecognizerSF_FR_COSINE)) for f in faces]
        best = max(sims)
        score = float(max(f[-1] for f in faces))
    return {"frame_index": index, "captured_at": time.time(), "faces": len(faces), "best_similarity": best,
            "detection_score": score, "brightness": brightness, "frame_hash": hashlib.sha256(img_bytes).hexdigest()[:16], "simulated": False}
