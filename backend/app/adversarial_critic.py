"""Agent 6 — Adversarial Critic. Challenges the other agents' conclusions with targeted questions.
It never overrides the policy engine; it can only force agents to defend, revise or retract."""
from .schemas import Challenge, Finding, FindingStatus as F

NAME, VERSION = "adversarial_critic", "1.0"


def _by_type(findings: list[Finding]) -> dict[str, Finding]:
    return {f.finding_type: f for f in findings if f.disposition != "retracted"}


def challenge(findings: list[Finding], round_no: int, already: set[tuple[str, str]]) -> list[Challenge]:
    """Returns new challenges for this round (never repeats a (finding, kind) pair)."""
    t = _by_type(findings)
    out: list[Challenge] = []

    def ask(f: Finding | None, kind: str, q: str):
        if f and (f.finding_id, kind) not in already:
            already.add((f.finding_id, kind))
            out.append(Challenge(round=round_no, target_finding_id=f.finding_id, target_agent=f.agent, question=q, kind=kind))

    voice, speaker, exam, life, risk, claim = (t.get(k) for k in ("voice_authenticity", "speaker_identity", "exam_identity", "number_lifecycle", "action_risk", "claim_consistency"))
    if voice and voice.status == F.NO_SYNTHETIC_INDICATORS:
        ask(voice, "authenticity_vs_identity", "The audio shows no synthetic indicators — does that establish WHO is speaking, or only that the audio seems human?")
    if voice and voice.status == F.SYNTHETIC_INDICATORS and speaker and speaker.status == F.SPEAKER_MATCH_SUPPORTED:
        ask(speaker, "clone_can_match", "The voice matches the enrolled speaker but shows synthetic indicators. Could a clone of the enrolled voice pass speaker verification?")
    if voice and voice.status == F.SYNTHETIC_INDICATORS and risk and risk.status != F.HIGH_RISK_ACTION:
        ask(voice, "suspicion_vs_intent", "Is a synthetic-voice suspicion being treated as proof of malicious intent for a low-risk request?")
    for f in (voice, speaker):
        if f and f.status in (F.UNAVAILABLE, F.NO_REFERENCE):
            ask(f, "missing_data", "Evidence is missing here. Is anyone treating missing data as evidence of fraud — or as a pass?")
    if exam and exam.status == F.FACE_MATCH_SUPPORTED:
        ask(exam, "similarity_vs_liveness", "A face match shows similarity. Does it prove a live person is present, or could a photo/replay produce it?")
    if exam and exam.status in (F.FACE_MISMATCH_SUSPECTED, F.LIVENESS_INCONCLUSIVE, F.NO_FACE_DETECTED):
        ask(exam, "benign_explanation", "Could lighting, camera quality, glasses or an accessibility need explain this without any impersonation?")
    if life and life.status in (F.NUMBER_REASSIGNMENT_SUSPECTED, F.UNCONFIRMED_REPORT):
        ask(life, "benign_explanation", "Could a legitimate relative who changed numbers explain this anomaly?")
    if claim and claim.status == F.CLAIM_ANOMALIES_FOUND:
        ask(claim, "benign_explanation", "Could each claim anomaly have a legitimate explanation (hospital stay, bank change, late paperwork)? Is the claim being treated as fraud on indicators alone?")
    if risk and risk.status == F.HIGH_RISK_ACTION:
        ask(risk, "mandatory_requirements", "Are the mandatory authentication requirements satisfied independently of any voice or face result?")
    return out


def unresolved(findings: list[Finding], challenges: list[Challenge]) -> list[str]:
    """Contradictions that survived the challenge rounds (kept visible, never smoothed over)."""
    t = _by_type(findings)
    issues = []
    voice, speaker, exam = t.get("voice_authenticity"), t.get("speaker_identity"), t.get("exam_identity")
    if voice and speaker and voice.status == F.NO_SYNTHETIC_INDICATORS and speaker.status == F.SPEAKER_MISMATCH_SUSPECTED:
        issues.append("Human-sounding voice that does not match the enrolled speaker: real person, but possibly not the claimed one.")
    if voice and speaker and voice.status == F.SYNTHETIC_INDICATORS and speaker.status in (F.SPEAKER_MATCH_SUPPORTED, F.SPEAKER_MATCH_NOT_SUFFICIENT):
        issues.append("Voiceprint matches but audio shows synthetic indicators: possible clone of the enrolled person.")
    if voice and voice.status == F.INCONCLUSIVE and speaker and speaker.status == F.SPEAKER_MATCH_SUPPORTED:
        issues.append("Speaker match with inconclusive authenticity: cannot rule out a high-quality clone.")
    claim = t.get("claim_consistency")
    if claim and claim.status == F.CLAIM_ANOMALIES_FOUND and voice and voice.status == F.NO_SYNTHETIC_INDICATORS and speaker and speaker.status == F.SPEAKER_MATCH_SUPPORTED:
        issues.append("Voice and voiceprint look genuine, but the claim record has anomalies: identity evidence and claim evidence disagree.")
    if exam and exam.status == F.MANUAL_REVIEW_REQUIRED:
        issues.append("Face results disagree across frames.")
    issues += [f"Unanswered challenge to {c.target_agent}: {c.question}" for c in challenges if c.outcome in (None, "unresolved")]
    return issues
