"""Agent 3 — Exam Identity (original core feature). Multi-frame decision on outputs of a real face model
(OpenCV YuNet detector + SFace embeddings, see face_service.py). No LLM ever judges a face."""
from .schemas import Challenge, Finding, FindingStatus as F, InvestigationRequest

NAME, VERSION = "exam_identity_agent", "1.0"
MIN_FRAMES = 3
DARK = 45  # mean brightness (0–255) below which a frame counts as low quality


def analyze(req: InvestigationRequest) -> Finding:
    frames = req.face_frames
    model = req.face_model or {}
    thr = model.get("threshold", 0.363)
    f = Finding(agent=NAME, agent_version=VERSION, scenario_id=req.scenario_id, finding_type="exam_identity", status=F.MANUAL_REVIEW_REQUIRED)
    f.evidence_refs = [f"frame:{fr.frame_index}{' [SIMULATED]' if fr.simulated else ''}" for fr in frames]
    f.limitations = [
        f"Model {model.get('name', 'OpenCV YuNet + SFace')} (cosine threshold {thr}, OpenCV's published value); lighting, camera quality and accessibility needs affect results.",
        "No presentation-attack (liveness) model: similarity cannot prove a live person.",
        "Investigation states only — never proof of cheating.",
    ]
    if not req.face_reference_enrolled:
        f.status, f.kind = F.REFERENCE_IMAGE_MISSING, "observed_fact"
        f.observations = ["No consented reference image enrolled for this student."]
        f.recommended_next_step = "Enroll a reference image with consent, or verify with a proctor."
        return f
    if not frames:
        f.status = F.NO_FACE_DETECTED
        f.observations = ["No usable image was received."]
        f.recommended_next_step = "Upload or capture an image."
        return f
    if len(frames) < MIN_FRAMES:
        f.warnings.append(f"Only {len(frames)} frame(s); multi-frame verification needs {MIN_FRAMES}.")
    multi = [fr for fr in frames if fr.faces > 1]
    none_ = [fr for fr in frames if fr.faces == 0]
    dark = [fr for fr in frames if fr.brightness is not None and fr.brightness < DARK]
    single = [fr for fr in frames if fr.faces == 1 and fr.best_similarity is not None]
    matches = [fr for fr in single if fr.best_similarity >= thr]
    hashes = {fr.frame_hash for fr in frames if fr.frame_hash}
    static = len(hashes) == 1 and len(frames) > 1
    f.observations = [
        f"{len(frames)} frames: {len(single)} with one face, {len(none_)} with none, {len(multi)} with several, {len(dark)} too dark.",
        f"Similarity per frame: {[round(fr.best_similarity, 3) if fr.best_similarity is not None else None for fr in frames]} (threshold {thr}).",
    ]
    if static:
        f.observations.append("All frames are pixel-identical: possible static image or replay (heuristic, not a liveness model).")
    if multi:
        f.status = F.MULTIPLE_FACES_DETECTED
        f.recommended_next_step = "Proctor review: more than one person visible."
    elif len(none_) > len(frames) / 2:
        f.status = F.NO_FACE_DETECTED
        f.recommended_next_step = "Ask the student to face the camera; re-verify."
    elif len(dark) > len(frames) / 2:
        f.status = F.LIVENESS_INCONCLUSIVE
        f.recommended_next_step = "Poor lighting or camera: improve conditions and re-verify. Do not accuse."
    elif static:
        f.status = F.LIVENESS_INCONCLUSIVE
        f.recommended_next_step = "Possible photo/replay: ask for live movement and re-verify."
    elif single and len(matches) >= max(min(MIN_FRAMES, len(frames)), int(0.6 * len(single) + 0.999)):
        f.status = F.FACE_MATCH_SUPPORTED
        f.recommended_next_step = "Allow start; re-verify periodically."
    elif single and len(matches) <= 0.2 * len(single):
        f.status = F.FACE_MISMATCH_SUSPECTED
        f.recommended_next_step = "Proctor review and re-verification."
    else:
        f.recommended_next_step = "Mixed results across frames: human review."
    return f


def respond(f: Finding, ch: Challenge, req: InvestigationRequest) -> Challenge:
    if ch.kind == "similarity_vs_liveness":
        f.limitations.append("Revised after critic: FACE_MATCH_SUPPORTED means similarity only; liveness remains unproven.")
        f.revision += 1
        f.disposition = "revised"
        ch.response, ch.outcome = "Agreed: the match supports identity similarity, not liveness. Logged as a limitation.", "revised"
    elif ch.kind == "benign_explanation":
        f.disposition = "defended"
        ch.response, ch.outcome = "Defended with caveat: a benign cause (lighting, angle, glasses) is possible, so this stays an investigation state, not an accusation.", "defended"
    else:
        ch.response, ch.outcome = "Defended: per-frame model outputs are attached as evidence.", "defended"
    return ch
