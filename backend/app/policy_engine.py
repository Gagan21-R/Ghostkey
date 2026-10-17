"""Deterministic authorization engine. No LLM or agent vote can override these rules (rule 12).

Agent findings are inputs; the outcome is decided only by explicit, testable requirements per profile.
"""
from __future__ import annotations

from .schemas import FindingStatus as F
from .schemas import InvestigationRequest, PolicyDecision, PolicyOutcome, ProviderStatus, Requirement

SENSITIVE_BANKING = {"pin_change", "password_reset", "recovery_change", "account_detail_change", "add_payee", "large_transfer"}
FAMILY_MONEY = {"emergency_transfer", "send_money"}
FORBIDDEN = {"share_otp", "share_password", "share_pin"}  # never authorized over a call, whoever asks

ROLE_PERMISSIONS = {
    "banking": {"customer": SENSITIVE_BANKING | {"balance_enquiry", "freeze_card"}, "support_agent": {"balance_enquiry", "freeze_card"}, "admin": SENSITIVE_BANKING},
    "family": {"family_member": FAMILY_MONEY | {"chat"}, "unknown_caller": {"chat"}, "customer": FAMILY_MONEY | {"chat"}},
    "exam": {"student": {"start_exam", "continue_exam"}, "proctor": {"review"}},
    "insurance": {"policyholder": {"submit_claim", "submit_high_value_claim", "change_payout_details", "change_contact_details", "add_nominee",
                                   "pay_premium", "claim_status", "freeze_payouts"},
                  "authorized_representative": {"submit_claim", "submit_high_value_claim"}, "claims_officer": {"review"}},
}
INSURANCE_SENSITIVE = {"change_payout_details", "submit_high_value_claim", "change_contact_details", "add_nominee"}
INSURANCE_PROTECTIVE = {"freeze_payouts"}  # protective actions can only help the policyholder: no extra checks

PROFILES = {
    "banking": "Banking security: sensitive changes need a fresh single-use challenge AND a trusted-device approval bound to the exact action. Voice evidence alone never authorizes.",
    "family": "Family & phone-number protection: money requests need independent verification over an enrolled channel; a familiar number or voice is never enough; OTP/PIN requests are always denied.",
    "insurance": "Insurance claims (synthetic demo): payout changes and high-value claims need a fresh challenge AND a simulated trusted-device approval bound to the exact claim and action; incomplete claims are held for documents; anomalies go to a claims officer, never an automatic fraud finding.",
    "exam": "Online examination: multi-frame face match on the enrolled reference, one person in view; uncertain or mismatched results go to human review — never an automatic accusation.",
}


def _status(findings: list, finding_type: str):
    for f in findings:
        if f.finding_type == finding_type and f.disposition != "retracted":
            return f.status
    return None


PROTECTIVE = {"freeze_card", "freeze_payouts"}  # can only help the account holder


def decide(req: InvestigationRequest, findings: list, unresolved: list[str]) -> PolicyDecision:
    d = _speaker_gate(req, findings, _decide(req, findings, unresolved))
    d.headline = d.headline or _headline(req, findings, d, unresolved)
    return d


def _speaker_gate(req: InvestigationRequest, findings: list, d: PolicyDecision) -> PolicyDecision:
    """R13: when the caller claims an identity that has a voiceprint and a speaker check was actually attempted,
    its result must be able to change the outcome. Before this rule, banking non-sensitive requests and family
    requests with independent verification were authorized whatever the speaker check said (the "same result for
    a different voice" bug). A check that was never attempted (speaker_verification None) is left to the profile."""
    if not (req.speaker_reference_enrolled and req.speaker_verification is not None):
        return d
    speaker = _status(findings, "speaker_identity")
    # A mismatch never authorizes. If strong independent checks also passed, the conflict goes to a reviewer
    # (scenario G); otherwise the identity claim is refused.
    if req.requested_action.type in PROTECTIVE or d.outcome != PolicyOutcome.VERIFIED_AND_AUTHORIZED:
        if speaker == F.SPEAKER_MISMATCH_SUSPECTED:
            d.reasons.append("The voice also does not match the claimed person's enrolled voiceprint.")
            if d.outcome in (PolicyOutcome.ESCALATED_FOR_REVIEW, PolicyOutcome.HOLD_FOR_VERIFICATION):
                d.headline = d.headline or ("Speaker mismatch detected — review required." if d.outcome == PolicyOutcome.ESCALATED_FOR_REVIEW
                                            else "Speaker mismatch detected.")
        return d
    p = req.speaker_verification
    who = req.claimed_identity or "the claimed person"
    score = f" (similarity {p.score} vs threshold {p.threshold})" if p.score is not None and p.threshold is not None else ""
    if speaker == F.SPEAKER_MISMATCH_SUSPECTED:
        d.requirements.append(Requirement(name="claimed_speaker_matches_voiceprint", satisfied=False, detail=f"no_match{score}"))
        d.rules_fired.append("R13: speaker mismatch on a claimed identity → not authorized")
        d.outcome = PolicyOutcome.DENIED
        d.reasons.append(f"Speaker mismatch: this voice does not match {who}'s enrolled voiceprint{score}. The identity claim is rejected; "
                         "confirm through an independent channel before acting.")
        d.headline = "Speaker mismatch detected."
    elif speaker in (F.UNAVAILABLE, F.INCONCLUSIVE, None):
        why = p.error or ("similarity too close to the threshold" if speaker == F.INCONCLUSIVE else "no result")
        d.requirements.append(Requirement(name="claimed_speaker_matches_voiceprint", satisfied=False, detail=f"not confirmed: {why}"))
        d.rules_fired.append("R13: requested speaker check did not confirm the claimed identity → hold")
        d.outcome = PolicyOutcome.HOLD_FOR_VERIFICATION
        d.reasons.append(f"The voiceprint check for {who} did not give a usable result ({why}). Held: retry with a clearer recording "
                         "of at least a few seconds of speech, or verify independently.")
        d.headline = "Speaker could not be confirmed — retry needed."
    elif speaker == F.SPEAKER_MATCH_SUPPORTED:
        d.requirements.append(Requirement(name="claimed_speaker_matches_voiceprint", satisfied=True, detail=f"match{score}"))
    return d


def _headline(req: InvestigationRequest, findings: list, d: PolicyDecision, unresolved: list) -> str:
    speaker, voice = _status(findings, "speaker_identity"), _status(findings, "voice_authenticity")
    O = PolicyOutcome
    if d.outcome == O.DENIED:
        if req.requested_action.type in FORBIDDEN:
            return "Request for a secret is always refused."
        if any("R7" in r for r in d.rules_fired):
            return "Role not permitted for this action."
        if any("R6" in r for r in d.rules_fired) or (req.challenge_check or {}).get("reason") == "replayed_challenge":
            return "Replayed verification code rejected."
        return "Request refused."
    if d.outcome == O.ESCALATED_FOR_REVIEW:
        if speaker == F.SPEAKER_MATCH_NOT_SUFFICIENT:
            return "Voiceprint matches but audio looks synthetic — possible clone."
        if voice == F.SYNTHETIC_INDICATORS:
            return "Synthetic voice indicators — human review required."
        if unresolved:
            return "Conflicting verification results — reviewer decides."
        if req.use_case == "exam":
            return "Face evidence needs proctor review."
        if _status(findings, "claim_consistency") == F.CLAIM_ANOMALIES_FOUND:
            return "Claim anomalies — a claims officer reviews (not a fraud finding)."
        return "Additional review required."
    if d.outcome == O.HOLD_FOR_VERIFICATION:
        if voice == F.SYNTHETIC_INDICATORS:
            return "Synthetic voice indicators — held."
        # name what is actually missing (the voice itself is never the missing piece)
        unmet = {r.name.split(" (")[0] for r in d.requirements if not r.satisfied and "informational" not in r.name and r.name != "role_permission"}
        if "independent_verification_over_enrolled_channel" in unmet:
            return "Independent verification not completed."
        if unmet & {"fresh_single_use_challenge", "trusted_device_approval_for_exact_action", "trusted_device_approval_for_exact_claim_action"}:
            return "One-time code and device approval required."
        if "required_documents_present" in unmet:
            return "Required claim documents missing."
        if unmet:
            return "Required identity evidence missing."
        return "Additional confirmation required."
    if req.use_case == "exam":
        return "Face matches the enrolled reference."
    if speaker == F.SPEAKER_MATCH_SUPPORTED:
        return "Speaker matches and requirements are met."
    return "All required checks passed."


def _decide(req: InvestigationRequest, findings: list, unresolved: list[str]) -> PolicyDecision:
    action = req.requested_action.type
    reqs: list[Requirement] = []
    rules: list[str] = []
    reasons: list[str] = []

    allowed = ROLE_PERMISSIONS.get(req.use_case, {}).get(req.actor_role, set())
    role_ok = action in allowed
    reqs.append(Requirement(name="role_permission", satisfied=role_ok, detail=f"role '{req.actor_role}' {'may' if role_ok else 'may not'} perform '{action}'"))

    # Provider availability is reported, never counted as a pass (rule 1).
    audio = req.audio_authenticity
    if audio and audio.status in (ProviderStatus.UNAVAILABLE, ProviderStatus.FAILED):
        rules.append("R1: detector unavailable/failed is not a successful detection")
        reasons.append(f"Voice-authenticity provider status {audio.status.value}: treated as missing evidence, not a pass.")

    ch = req.challenge_check or {}
    if ch and not ch.get("valid"):
        rules.append("R6: stale/reused/invalid challenge cannot authorize")
    ap = req.approval_check or {}
    if ap.get("reason") == "action_changed_after_approval":
        rules.append("R8: action changed after approval → earlier approval invalid")

    if action in FORBIDDEN:
        rules.append("Forbidden action: OTP/PIN/password are never disclosed over a call")
        reqs.append(Requirement(name="never_share_secrets", satisfied=False, detail="Requests to share OTPs, PINs or passwords are always denied."))
        return PolicyDecision(outcome=PolicyOutcome.DENIED, profile=PROFILES[req.use_case], requirements=reqs, rules_fired=rules,
                              reasons=reasons + ["The caller asked for a secret that must never be shared, regardless of who they are."])

    if not role_ok:
        rules.append("R7: unauthorized role")
        return PolicyDecision(outcome=PolicyOutcome.DENIED, profile=PROFILES[req.use_case], requirements=reqs, rules_fired=rules,
                              reasons=reasons + [f"Role '{req.actor_role}' is not permitted to perform '{action}'."])

    if req.use_case == "banking":
        return _banking(req, findings, unresolved, reqs, rules, reasons)
    if req.use_case == "family":
        return _family(req, findings, unresolved, reqs, rules, reasons)
    if req.use_case == "insurance":
        return _insurance(req, findings, unresolved, reqs, rules, reasons)
    return _exam(req, findings, unresolved, reqs, rules, reasons)


def _banking(req, findings, unresolved, reqs, rules, reasons) -> PolicyDecision:
    action = req.requested_action.type
    if action == "freeze_card":
        return PolicyDecision(outcome=PolicyOutcome.VERIFIED_AND_AUTHORIZED, profile=PROFILES["banking"], requirements=reqs, rules_fired=rules + ["Protective action"],
                              reasons=reasons + ["Freezing a card can only protect the customer, so it happens immediately; unfreezing needs full verification."])
    if action not in SENSITIVE_BANKING:
        return PolicyDecision(outcome=PolicyOutcome.VERIFIED_AND_AUTHORIZED, profile=PROFILES["banking"], requirements=reqs, rules_fired=rules,
                              reasons=reasons + ["Non-sensitive request: no additional verification required."])
    ch = req.challenge_check or {}
    ap = req.approval_check or {}
    ch_ok, ap_ok = bool(ch.get("valid")), bool(ap.get("valid"))
    if ch.get("reason") == "replayed_challenge":
        reqs.append(Requirement(name="fresh_single_use_challenge", satisfied=False, detail="replayed_challenge"))
        return PolicyDecision(outcome=PolicyOutcome.DENIED, profile=PROFILES["banking"], requirements=reqs, rules_fired=rules,
                              reasons=reasons + ["A challenge that was already used was submitted again: this attempt is rejected and recorded."])
    reqs.append(Requirement(name="fresh_single_use_challenge", satisfied=ch_ok, detail=ch.get("reason", "no challenge completed")))
    reqs.append(Requirement(name="trusted_device_approval_for_exact_action", satisfied=ap_ok, detail=ap.get("reason", "no approval")))
    voice = _status(findings, "voice_authenticity")
    speaker = _status(findings, "speaker_identity")
    reqs.append(Requirement(name="voice_evidence (informational only)", satisfied=voice == F.NO_SYNTHETIC_INDICATORS,
                            detail=f"voice: {voice.value if voice else 'none'}; speaker: {speaker.value if speaker else 'none'} — R3: never sufficient on its own"))
    rules.append("R3: voice authenticity alone cannot authorize banking changes")

    if ch_ok and ap_ok:
        if unresolved:
            rules.append("R9: contradictory evidence → escalate")
            return PolicyDecision(outcome=PolicyOutcome.ESCALATED_FOR_REVIEW, profile=PROFILES["banking"], requirements=reqs, rules_fired=rules,
                                  reasons=reasons + [f"Authentication passed but {len(unresolved)} agent disagreement(s) remain unresolved: a reviewer decides."])
        if voice == F.SYNTHETIC_INDICATORS:
            rules.append("R9/R10: synthetic indicators with otherwise complete auth → human review, not automatic denial")
            return PolicyDecision(outcome=PolicyOutcome.ESCALATED_FOR_REVIEW, profile=PROFILES["banking"], requirements=reqs, rules_fired=rules,
                                  reasons=reasons + ["Independent authentication passed, but the call audio shows synthetic indicators: a reviewer confirms before the change."])
        return PolicyDecision(outcome=PolicyOutcome.VERIFIED_AND_AUTHORIZED, profile=PROFILES["banking"], requirements=reqs, rules_fired=rules,
                              reasons=reasons + ["Fresh challenge and trusted-device approval for this exact action are both present."])
    missing = [r.name for r in reqs if not r.satisfied and "informational" not in r.name and r.name != "role_permission"]
    if unresolved:
        reasons.append(f"Unresolved agent disagreements: {len(unresolved)}.")
    return PolicyDecision(outcome=PolicyOutcome.HOLD_FOR_VERIFICATION, profile=PROFILES["banking"], requirements=reqs, rules_fired=rules + ["R2: missing authentication evidence is not a pass"],
                          reasons=reasons + [f"Held: mandatory evidence missing ({', '.join(missing)}). The voice — however genuine it sounds — cannot replace it."])


def _family(req, findings, unresolved, reqs, rules, reasons) -> PolicyDecision:
    if req.requested_action.type == "chat":
        return PolicyDecision(outcome=PolicyOutcome.VERIFIED_AND_AUTHORIZED, profile=PROFILES["family"], requirements=reqs, rules_fired=rules,
                              reasons=reasons + ["Nothing sensitive was requested: talking is fine, but nothing should be sent until identity is verified."])
    iv = req.independent_verification or {}
    iv_ok = iv.get("status") == "passed"
    reqs.append(Requirement(name="independent_verification_over_enrolled_channel", satisfied=iv_ok,
                            detail=f"{iv.get('method', 'none')}: {iv.get('status', 'not completed')}"))
    lifecycle = _status(findings, "number_lifecycle")
    rules.append("R5: a phone number never establishes identity")
    if lifecycle in (F.NUMBER_REASSIGNMENT_SUSPECTED, F.ACCOUNT_TAKEOVER_SUSPECTED):
        reasons.append(f"Number lifecycle: {lifecycle.value} (simulated carrier event).")
    voice = _status(findings, "voice_authenticity")
    if iv_ok:
        if voice == F.SYNTHETIC_INDICATORS or unresolved:
            return PolicyDecision(outcome=PolicyOutcome.ESCALATED_FOR_REVIEW, profile=PROFILES["family"], requirements=reqs, rules_fired=rules,
                                  reasons=reasons + ["Independent verification passed but evidence conflicts; the family member confirms in person or by video before money moves."])
        return PolicyDecision(outcome=PolicyOutcome.VERIFIED_AND_AUTHORIZED, profile=PROFILES["family"], requirements=reqs, rules_fired=rules,
                              reasons=reasons + ["Identity confirmed independently over the enrolled recovery channel; the request may proceed."])
    return PolicyDecision(outcome=PolicyOutcome.HOLD_FOR_VERIFICATION, profile=PROFILES["family"], requirements=reqs, rules_fired=rules + ["R2: missing authentication evidence is not a pass"],
                          reasons=reasons + ["Held: the caller has not completed independent verification. Alert sent to the protected person's trusted contacts."])


def _insurance(req, findings, unresolved, reqs, rules, reasons) -> PolicyDecision:
    action = req.requested_action.type
    P = PROFILES["insurance"]
    claim = _status(findings, "claim_consistency")
    voice = _status(findings, "voice_authenticity")
    speaker = _status(findings, "speaker_identity")
    c = req.claim or {}
    missing = sorted(set(c.get("required_documents", [])) - set(c.get("documents", [])))
    reqs.append(Requirement(name="required_documents_present", satisfied=not missing, detail="all present" if not missing else "missing: " + ", ".join(missing)))
    rules.append("R3: a voice result alone never authorizes a payout or claim change")
    if action in INSURANCE_PROTECTIVE:
        return PolicyDecision(outcome=PolicyOutcome.VERIFIED_AND_AUTHORIZED, profile=P, requirements=reqs, rules_fired=rules + ["Protective action"],
                              reasons=reasons + ["Freezing payouts only protects the policyholder, so it is done immediately; unfreezing needs full verification."])
    if action in ("pay_premium", "claim_status"):
        return PolicyDecision(outcome=PolicyOutcome.VERIFIED_AND_AUTHORIZED, profile=P, requirements=reqs, rules_fired=rules,
                              reasons=reasons + ["Low-risk request (no money leaves the policy and no details change)."])
    if action not in INSURANCE_SENSITIVE:
        if missing:
            return PolicyDecision(outcome=PolicyOutcome.HOLD_FOR_VERIFICATION, profile=P, requirements=reqs, rules_fired=rules + ["R2: missing evidence is not a pass"], reasons=reasons + ["Held until the missing documents arrive."])
        if claim == F.CLAIM_ANOMALIES_FOUND or unresolved:
            return PolicyDecision(outcome=PolicyOutcome.ESCALATED_FOR_REVIEW, profile=P, requirements=reqs, rules_fired=rules, reasons=reasons + ["Claim anomalies need a claims officer's review (not a fraud finding)."])
        return PolicyDecision(outcome=PolicyOutcome.VERIFIED_AND_AUTHORIZED, profile=P, requirements=reqs, rules_fired=rules,
                              reasons=reasons + ["Standard claim submission with complete documents: accepted for normal claims processing."])
    ch, ap = req.challenge_check or {}, req.approval_check or {}
    if ch.get("reason") == "replayed_challenge":
        return PolicyDecision(outcome=PolicyOutcome.DENIED, profile=P, requirements=reqs, rules_fired=rules + ["R6: replayed challenge"], reasons=reasons + ["Replayed challenge rejected and recorded."])
    ch_ok, ap_ok = bool(ch.get("valid")), bool(ap.get("valid"))
    reqs.append(Requirement(name="fresh_single_use_challenge", satisfied=ch_ok, detail=ch.get("reason", "no challenge completed")))
    reqs.append(Requirement(name="trusted_device_approval_for_exact_claim_action (simulated device)", satisfied=ap_ok, detail=ap.get("reason", "no approval")))
    voice_needed = req.speaker_reference_enrolled and action == "change_payout_details"
    if voice_needed:
        done = voice not in (None, F.UNAVAILABLE)
        reqs.append(Requirement(name="voice_check_completed (mandatory: voiceprint on file)", satisfied=done, detail=voice.value if voice else "not run"))
        if not done:
            rules.append("R1: provider failure during a mandatory voice check")
            return PolicyDecision(outcome=PolicyOutcome.HOLD_FOR_VERIFICATION, profile=P, requirements=reqs, rules_fired=rules, reasons=reasons + ["Mandatory voice check did not complete: held, not passed."])
    if speaker == F.SPEAKER_MISMATCH_SUSPECTED and voice_needed:
        rules.append("Failed mandatory check: escalate (never an automatic fraud verdict)")
        return PolicyDecision(outcome=PolicyOutcome.ESCALATED_FOR_REVIEW, profile=P, requirements=reqs, rules_fired=rules,
                              reasons=reasons + ["The caller's voice does not match the policyholder's voiceprint: a claims officer verifies identity before any payout change."])
    if missing or not (ch_ok and ap_ok):
        unmet = [r.name for r in reqs if not r.satisfied and r.name != "role_permission"]
        return PolicyDecision(outcome=PolicyOutcome.HOLD_FOR_VERIFICATION, profile=P, requirements=reqs, rules_fired=rules + ["R2: missing evidence is not a pass"],
                              reasons=reasons + [f"Held — unmet requirements: {', '.join(unmet)}. The caller's voice, however genuine it sounds, cannot replace them."])
    if claim == F.CLAIM_ANOMALIES_FOUND or voice == F.SYNTHETIC_INDICATORS or unresolved:
        return PolicyDecision(outcome=PolicyOutcome.ESCALATED_FOR_REVIEW, profile=P, requirements=reqs, rules_fired=rules + ["R9: conflicting evidence"],
                              reasons=reasons + ["Authentication passed, but claim anomalies or conflicting evidence remain: a claims officer decides."])
    return PolicyDecision(outcome=PolicyOutcome.VERIFIED_AND_AUTHORIZED, profile=P, requirements=reqs, rules_fired=rules,
                          reasons=reasons + ["Fresh challenge and action-bound approval present, documents complete, no anomalies."])


def _exam(req, findings, unresolved, reqs, rules, reasons) -> PolicyDecision:
    face = _status(findings, "exam_identity")
    reqs.append(Requirement(name="multi_frame_face_match", satisfied=face == F.FACE_MATCH_SUPPORTED, detail=face.value if face else "no result"))
    reqs.append(Requirement(name="liveness_proven", satisfied=False, detail="No presentation-attack model: R4 — similarity alone never proves liveness"))
    rules.append("R4: facial similarity alone does not prove liveness")
    rules.append("R11: uncertain outcomes keep a human-review option")
    frames = len(req.face_frames)
    reqs.append(Requirement(name="at_least_3_frames", satisfied=frames >= 3, detail=f"{frames} frame(s) analysed"))
    if face == F.FACE_MATCH_SUPPORTED and frames < 3:
        return PolicyDecision(outcome=PolicyOutcome.HOLD_FOR_VERIFICATION, profile=PROFILES["exam"], requirements=reqs, rules_fired=rules,
                              reasons=reasons + ["Single-image match: re-verify with at least 3 live frames before the exam starts."])
    if face == F.FACE_MATCH_SUPPORTED and not unresolved:
        return PolicyDecision(outcome=PolicyOutcome.VERIFIED_AND_AUTHORIZED, profile=PROFILES["exam"], requirements=reqs, rules_fired=rules,
                              reasons=reasons + ["Face matches the enrolled reference across frames; exam may start with periodic re-verification. Liveness remains unproven and is logged."])
    if face in (F.FACE_MISMATCH_SUSPECTED, F.MULTIPLE_FACES_DETECTED) or unresolved:
        return PolicyDecision(outcome=PolicyOutcome.ESCALATED_FOR_REVIEW, profile=PROFILES["exam"], requirements=reqs, rules_fired=rules,
                              reasons=reasons + ["Investigation state, not proof of cheating: a proctor reviews the evidence and may re-verify the student."])
    return PolicyDecision(outcome=PolicyOutcome.HOLD_FOR_VERIFICATION, profile=PROFILES["exam"], requirements=reqs, rules_fired=rules,
                          reasons=reasons + ["Evidence inconclusive (camera, lighting, or missing reference): re-verify with better conditions or an alternative check — no accusation."])
