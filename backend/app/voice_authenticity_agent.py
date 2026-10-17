"""Agent 1 — Voice Authenticity. Interprets DetectifAI's audio-authenticity result. Never infers identity."""
from .schemas import Challenge, Finding, FindingStatus as F, InvestigationRequest, ProviderStatus

NAME, VERSION = "voice_authenticity_agent", "1.0"


def analyze(req: InvestigationRequest) -> Finding:
    p = req.audio_authenticity
    f = Finding(agent=NAME, agent_version=VERSION, scenario_id=req.scenario_id, finding_type="voice_authenticity", status=F.UNAVAILABLE)
    if p is None:
        f.observations = ["No audio was analysed."]
        f.recommended_next_step = "Collect a recording longer than 4 seconds."
        return f
    tag = " [SIMULATED fixture]" if p.simulated else " [live DetectifAI result]"
    f.evidence_refs = [f"{p.provider}:{p.raw_result_reference or 'n/a'}{tag}"]
    f.limitations = list(p.limitations) + ["A human-sounding voice says nothing about WHO is speaking."]
    if p.status in (ProviderStatus.UNAVAILABLE, ProviderStatus.FAILED, ProviderStatus.NOT_SUPPORTED):
        f.observations = [f"Provider status {p.status.value}: {p.error or ''}".strip()]
        f.recommended_next_step = "Treat as missing evidence; do not count as passed or failed."
        f.kind = "observed_fact"
        return f
    f.observations = [f"DetectifAI verdict '{p.classification}', score {p.score} (threshold {p.threshold}; {p.score_semantics})."] + p.evidence_summary[1:]
    if p.classification == "fake":
        f.status = F.SYNTHETIC_INDICATORS
        f.recommended_next_step = "Do not rely on this voice; require independent verification."
    elif p.classification == "real":
        f.status = F.NO_SYNTHETIC_INDICATORS
        f.recommended_next_step = "No synthetic indicators; identity still needs separate evidence."
    else:
        f.status = F.INCONCLUSIVE
        f.recommended_next_step = "Inconclusive: gather more audio or use an independent check."
    return f


def respond(f: Finding, ch: Challenge, req: InvestigationRequest) -> Challenge:
    if ch.kind == "authenticity_vs_identity":
        f.limitations.append("Revised after critic: this finding covers synthesis indicators only, not caller identity.")
        f.recommended_next_step = "Identity must come from speaker verification or independent authentication."
        f.revision += 1
        f.disposition = "revised"
        ch.response, ch.outcome = "Agreed. The finding is limited to synthesis indicators; it does not identify the caller.", "revised"
    elif ch.kind == "suspicion_vs_intent":
        f.disposition = "defended"
        ch.response, ch.outcome = "Defended: synthetic indicators are reported as a risk signal only, not as proof of malicious intent.", "defended"
    else:
        ch.response, ch.outcome = "No change: the provider output is reported verbatim with its limitations.", "defended"
    return ch
