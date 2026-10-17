"""Agent 2 — Speaker Identity. Uses DetectifAI speaker verification against an enrolled voiceprint.
Never asks an LLM whether voices sound alike."""
from .schemas import Challenge, Finding, FindingStatus as F, InvestigationRequest, ProviderStatus

NAME, VERSION = "speaker_identity_agent", "1.0"
MARGIN = 0.05  # within ±0.05 of the provider threshold → inconclusive


def analyze(req: InvestigationRequest) -> Finding:
    p = req.speaker_verification
    f = Finding(agent=NAME, agent_version=VERSION, scenario_id=req.scenario_id, finding_type="speaker_identity", status=F.UNAVAILABLE)
    if not req.speaker_reference_enrolled:
        f.status, f.kind = F.NO_REFERENCE, "observed_fact"
        f.observations = ["No enrolled voiceprint for the claimed identity."]
        f.recommended_next_step = "Identity cannot be checked by voice; use an independent channel."
        return f
    if p is None or p.status in (ProviderStatus.UNAVAILABLE, ProviderStatus.FAILED):
        f.observations = [f"Speaker verification unavailable: {p.error if p else 'not run'}"]
        f.recommended_next_step = "Missing evidence — not a pass."
        return f
    tag = " [SIMULATED fixture]" if p.simulated else " [live DetectifAI result]"
    f.evidence_refs = [f"{p.provider}:{p.raw_result_reference or 'n/a'}{tag}"]
    f.limitations = list(p.limitations)
    sim, thr = p.score, p.threshold
    f.observations = [f"DetectifAI decision '{p.classification}', similarity {sim} vs threshold {thr} ({p.score_semantics})."]
    if sim is not None and thr is not None and abs(sim - thr) < MARGIN:
        f.status = F.INCONCLUSIVE
        f.recommended_next_step = "Similarity is close to the threshold; use an independent check."
    elif p.classification == "match":
        f.status = F.SPEAKER_MATCH_SUPPORTED
        f.recommended_next_step = "Voice matches the enrolled speaker; still confirm the audio is not synthetic."
    else:
        f.status = F.SPEAKER_MISMATCH_SUSPECTED
        f.recommended_next_step = "Voice does not match the enrolled speaker; require independent verification."
    return f


def respond(f: Finding, ch: Challenge, req: InvestigationRequest) -> Challenge:
    if ch.kind == "clone_can_match" and f.status == F.SPEAKER_MATCH_SUPPORTED:
        f.history.append({"revision": f.revision, "status": f.status.value})
        f.status, f.revision, f.disposition = F.SPEAKER_MATCH_NOT_SUFFICIENT, f.revision + 1, "revised"
        f.contradictions.append("Voice agent reports synthetic indicators while the voiceprint matches: consistent with a voice clone.")
        ch.response, ch.outcome = "Revised: a clone of the enrolled voice can match the voiceprint, so the match is not sufficient evidence of identity here.", "revised"
    elif ch.kind == "missing_data":
        f.disposition = "defended"
        ch.response, ch.outcome = "Defended: a missing reference is reported as missing, not as a mismatch.", "defended"
    else:
        ch.response, ch.outcome = "Defended: result reported with the provider's own threshold semantics.", "defended"
    return ch
