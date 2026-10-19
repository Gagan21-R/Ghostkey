"""Deterministic demo scenarios. Inputs marked simulated=True are labelled fixtures, never presented as
real DetectifAI results. Scenarios E and K can optionally call the live DetectifAI API on bundled audio.
Scenarios H, I and J exercise real code paths (network failure, real challenge replay, real approval hash)."""
from __future__ import annotations

import os
import time

from . import orchestrator, session_service
from .detectify_provider import DetectifyProvider, provider
from .insurance_data import CLAIMS, POLICYHOLDERS
from .schemas import FaceFrame, InvestigationRequest, ProviderResult, ProviderStatus, RequestedAction

SAMPLES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "samples")
LIVE_SPEAKER_ID = ((os.getenv("GHOSTKEY_DEMO_SPEAKER_ID") or "").strip().strip("'\"").strip() or "cust-zira-rao-7d3e")  # enrolled earlier on this DetectifAI account


def audio_fx(verdict: str, score: float) -> ProviderResult:
    return ProviderResult(capability="audio_authenticity", status=ProviderStatus.INCONCLUSIVE if verdict == "not_sure" else ProviderStatus.COMPLETED,
                          classification=verdict, score=score, threshold=0.62, simulated=True,
                          score_semantics="0–1, higher = more likely AI-generated (vendor score)",
                          evidence_summary=[f"SIMULATED fixture: verdict={verdict} score={score}"], raw_result_reference="fixture",
                          limitations=["SIMULATED fixture — not a DetectifAI response."])


def speaker_fx(decision: str, sim: float) -> ProviderResult:
    return ProviderResult(capability="speaker_verification", status=ProviderStatus.COMPLETED, classification=decision, score=sim, threshold=0.53,
                          simulated=True, score_semantics="similarity -1..1, not a percentage", raw_result_reference="fixture",
                          evidence_summary=[f"SIMULATED fixture: decision={decision} similarity={sim}"],
                          limitations=["SIMULATED fixture — not a DetectifAI response.", "A speaker match does not show the audio is human."])


def frames_fx(sims, brightness=120.0, faces=1) -> list[FaceFrame]:
    now = time.time()
    return [FaceFrame(frame_index=i, captured_at=now + i * 2, faces=faces, best_similarity=s, detection_score=0.9, brightness=brightness,
                      frame_hash=f"fx{i}", simulated=True) for i, s in enumerate(sims)]


def _valid_banking_checks(action: dict) -> tuple[dict, dict, str]:
    s = session_service.create_session("banking", "id-zira", action)
    c = session_service.issue_challenge(s["session_id"])
    ch = session_service.verify_challenge(s["session_id"], c["challenge_id"], c["nonce_for_trusted_channel"])
    a = session_service.request_approval(s["session_id"], action, "Zira's registered phone")
    session_service.decide_approval(a["approval_id"], True, "Zira's registered phone")
    return ch, session_service.check_approval(a["approval_id"], action), s["session_id"]


def _live_audio(name: str):
    path = os.path.join(SAMPLES, name)
    with open(path, "rb") as fh:
        data = fh.read()
    speaker, df = provider.speaker_verification(data, LIVE_SPEAKER_ID, filename=name)
    return df or provider.audio_authenticity(data, filename=name), speaker


SCENARIOS = {
    "A": {"title": "Family impersonation after number reassignment", "use_case": "family", "expected": "HOLD_FOR_VERIFICATION", "live": False},
    "B": {"title": "Legitimate family member after a number change", "use_case": "family", "expected": "VERIFIED_AND_AUTHORIZED", "live": False},
    "C": {"title": "Exam impersonation (substitute person)", "use_case": "exam", "expected": "ESCALATED_FOR_REVIEW", "live": False},
    "D": {"title": "Legitimate student, poor lighting", "use_case": "exam", "expected": "HOLD_FOR_VERIFICATION", "live": False},
    "E": {"title": "Banking voice clone requests a PIN change", "use_case": "banking", "expected": "HOLD_FOR_VERIFICATION", "live": True},
    "F": {"title": "Authentic voice, unauthorized recovery change", "use_case": "banking", "expected": "HOLD_FOR_VERIFICATION", "live": False},
    "G": {"title": "Agent disagreement on a payee change", "use_case": "banking", "expected": "ESCALATED_FOR_REVIEW", "live": False},
    "H": {"title": "DetectifAI unreachable", "use_case": "banking", "expected": "HOLD_FOR_VERIFICATION", "live": False},
    "I": {"title": "Replayed challenge", "use_case": "banking", "expected": "DENIED", "live": False},
    "J": {"title": "Approval reused for a modified action", "use_case": "banking", "expected": "HOLD_FOR_VERIFICATION", "live": False},
    "K": {"title": "Legitimate caller, inconclusive detector, completes authentication", "use_case": "banking", "expected": "VERIFIED_AND_AUTHORIZED", "live": False},
    "L": {"title": "Insurance: legitimate hospitalisation claim", "use_case": "insurance", "expected": "VERIFIED_AND_AUTHORIZED", "live": False},
    "M": {"title": "Insurance: cloned voice asks to change payout account", "use_case": "insurance", "expected": "HOLD_FOR_VERIFICATION", "live": False},
    "N": {"title": "Insurance: incomplete high-value claim", "use_case": "insurance", "expected": "HOLD_FOR_VERIFICATION", "live": False},
    "O": {"title": "Insurance: ambiguous nominee claim (possible duplicate)", "use_case": "insurance", "expected": "ESCALATED_FOR_REVIEW", "live": False},
    "P": {"title": "Family: suspected synthetic-voice money request", "use_case": "family", "expected": "HOLD_FOR_VERIFICATION", "live": False},
    "Q": {"title": "Family: suspicious request, inconclusive voice evidence", "use_case": "family", "expected": "HOLD_FOR_VERIFICATION", "live": False},
}


def _valid_checks(use_case: str, identity: str, action: dict, device: str) -> tuple[dict, dict]:
    s = session_service.create_session(use_case, identity, action)
    c = session_service.issue_challenge(s["session_id"])
    ch = session_service.verify_challenge(s["session_id"], c["challenge_id"], c["nonce_for_trusted_channel"])
    a = session_service.request_approval(s["session_id"], action, device)
    session_service.decide_approval(a["approval_id"], True, device)
    return ch, session_service.check_approval(a["approval_id"], action)


def _insurance(sid: str, base: dict) -> InvestigationRequest:
    claim_id = {"L": "CLM-2026-1042", "M": "CLM-2026-1077", "N": "CLM-2026-1103", "O": "CLM-2026-1121"}[sid]
    claim = CLAIMS[claim_id]
    ph = POLICYHOLDERS[claim["policyholder_id"]]
    action = RequestedAction(type=claim["requested_action"], amount=claim["amount"], details={"claim_id": claim_id, "new_payout_account": claim["new_payout_account"]})
    common = dict(**base, identity_id=ph["id"], claimed_identity=claim["claimant"], requested_action=action, claim=claim, policyholder=ph,
                  speaker_reference_enrolled=ph["voice_enrolled"])
    if sid == "L":
        return InvestigationRequest(**common, actor_role="policyholder", transcript="Hello, I'm submitting my hospitalisation claim; the documents are uploaded.",
                                    audio_authenticity=audio_fx("real", 0.02), speaker_verification=speaker_fx("match", 0.76))
    if sid == "M":
        return InvestigationRequest(**common, actor_role="policyholder", transcript="This is Anita. Please send my claim payout to my new account ending 7765 today, it's urgent.",
                                    audio_authenticity=audio_fx("fake", 0.998), speaker_verification=speaker_fx("match", 0.88))
    if sid == "N":
        return InvestigationRequest(**common, actor_role="policyholder", transcript="I need the six lakh car claim processed, I'll send the rest of the papers later.",
                                    audio_authenticity=audio_fx("real", 0.04))
    ch, ap = _valid_checks("insurance", ph["id"], action.model_dump(), "Policyholder's registered phone (simulated)")
    return InvestigationRequest(**common, actor_role="authorized_representative", transcript="I'm Imran, Fatima's brother and nominee, submitting her critical illness claim.",
                                audio_authenticity=audio_fx("not_sure", 0.55), challenge_check=ch, approval_check=ap)


def _family_extra(sid: str, base: dict) -> InvestigationRequest:
    if sid == "P":
        return InvestigationRequest(**base, identity_id="id-asha", claimed_identity="Asha's son Rohan", actor_role="family_member",
                                    requested_action=RequestedAction(type="emergency_transfer", amount=75000, details={"to": "unknown UPI ID"}),
                                    transcript="Ma, it's Rohan. I've been arrested, send 75,000 immediately and don't tell anyone.",
                                    audio_authenticity=audio_fx("fake", 0.97), speaker_verification=speaker_fx("match", 0.83), speaker_reference_enrolled=True,
                                    independent_verification={"method": "callback_to_enrolled_recovery_number", "status": "not completed"})
    return InvestigationRequest(**base, identity_id="id-asha", claimed_identity="Asha's daughter Meera", actor_role="family_member",
                                requested_action=RequestedAction(type="send_money", amount=20000, details={"to": "new account"}),
                                transcript="Hi Ma, it's Meera, my phone broke, can you quickly send 20,000 to this new account?",
                                audio_authenticity=audio_fx("not_sure", 0.52), speaker_verification=speaker_fx("match", 0.55), speaker_reference_enrolled=True,
                                independent_verification={"method": "code_on_enrolled_recovery_email", "status": "failed"})


def build(sid: str, live: bool = False) -> InvestigationRequest:
    meta = SCENARIOS[sid]
    base = dict(scenario_id=sid, title=f"Scenario {sid}: {meta['title']}", use_case=meta["use_case"])
    if sid == "A":
        return InvestigationRequest(**base, identity_id="id-asha", claimed_identity="Asha's son Rohan", actor_role="family_member",
                                    requested_action=RequestedAction(type="emergency_transfer", amount=50000, details={"to": "new UPI ID"}),
                                    transcript="Ma it's Rohan, I had an accident, I'm in hospital, send 50,000 right now, don't tell papa.",
                                    audio_authenticity=audio_fx("real", 0.031), speaker_verification=speaker_fx("no_match", 0.21), speaker_reference_enrolled=True,
                                    carrier_events=[{"type": "number_reassigned", "number": "+91 98450 XXXXX", "days_inactive": 120, "simulated": True}],
                                    independent_verification={"method": "callback_to_enrolled_recovery_number", "status": "failed"})
    if sid == "B":
        return InvestigationRequest(**base, identity_id="id-asha", claimed_identity="Asha's son Rohan", actor_role="family_member",
                                    requested_action=RequestedAction(type="send_money", amount=5000, details={"to": "Rohan's verified account"}),
                                    transcript="Hi Ma, it's Rohan, my new number. Can you send 5,000 for the course fee when you can?",
                                    audio_authenticity=audio_fx("real", 0.012), speaker_verification=speaker_fx("match", 0.74), speaker_reference_enrolled=True,
                                    carrier_events=[{"type": "number_reassigned", "number": "+91 98450 XXXXX", "note": "old number retired by Rohan", "simulated": True}],
                                    independent_verification={"method": "code_on_enrolled_recovery_email", "status": "passed"})
    if sid == "C":
        return InvestigationRequest(**base, identity_id="id-rahul", claimed_identity="Rahul Verma (student)", actor_role="student",
                                    requested_action=RequestedAction(type="start_exam", details={"exam": "Finance 101 midterm"}),
                                    face_frames=frames_fx([0.11, 0.09, 0.14, 0.12, 0.10]), face_reference_enrolled=True,
                                    face_model={"name": "OpenCV YuNet + SFace (SIMULATED frame outputs)", "threshold": 0.363})
    if meta["use_case"] == "insurance":
        return _insurance(sid, base)
    if sid in ("P", "Q"):
        return _family_extra(sid, base)
    if sid == "D":
        return InvestigationRequest(**base, identity_id="id-rahul", claimed_identity="Rahul Verma (student)", actor_role="student",
                                    requested_action=RequestedAction(type="start_exam", details={"exam": "Finance 101 midterm"}),
                                    face_frames=frames_fx([0.31, None, 0.29, 0.34, None], brightness=28.0), face_reference_enrolled=True,
                                    face_model={"name": "OpenCV YuNet + SFace (SIMULATED frame outputs)", "threshold": 0.363})
    action = {
        "E": RequestedAction(type="pin_change", details={"channel": "phone"}),
        "F": RequestedAction(type="recovery_change", details={"new_recovery_email": "zr.recovery@example.com"}),
        "G": RequestedAction(type="add_payee", amount=200000, details={"payee": "R. Kumar"}),
        "H": RequestedAction(type="add_payee", amount=40000, details={"payee": "S. Iyer"}),
        "I": RequestedAction(type="pin_change", details={"channel": "phone"}),
        "J": RequestedAction(type="add_payee", amount=10000, details={"payee": "Ravi (brother)"}),
        "K": RequestedAction(type="account_detail_change", details={"field": "mailing address"}),
    }[sid]
    common = dict(**base, identity_id="id-zira", claimed_identity="Zira Rao (customer)", actor_role="customer", requested_action=action, speaker_reference_enrolled=True)
    if sid == "E":
        if live:
            audio, speaker = _live_audio("clone-call.wav")
        else:
            audio, speaker = audio_fx("fake", 0.9994), speaker_fx("match", 0.91)
        return InvestigationRequest(**common, transcript="Hi, it's Zira. I forgot my PIN, please reset it now, I'm travelling.", audio_authenticity=audio, speaker_verification=speaker)
    if sid == "F":
        return InvestigationRequest(**common, transcript="Hello, this is Zira, please change my recovery email.",
                                    audio_authenticity=audio_fx("real", 0.02), speaker_verification=speaker_fx("match", 0.78),
                                    challenge_check={"valid": True, "reason": "fresh_single_use_challenge_passed"}, approval_check={"valid": False, "reason": "no_approval"})
    if sid == "G":
        ch, ap, _ = _valid_banking_checks(action.model_dump())
        return InvestigationRequest(**common, transcript="Add R. Kumar as a payee, I'll send two lakh today.",
                                    audio_authenticity=audio_fx("real", 0.03), speaker_verification=speaker_fx("no_match", 0.30), challenge_check=ch, approval_check=ap)
    if sid == "H":
        unreachable = DetectifyProvider(api_key=provider.api_key or "x", base_url="https://detectif.unreachable.invalid", max_retries=1)
        audio = unreachable.audio_authenticity(b"RIFF....WAVE", filename="call.wav")  # real network failure path
        return InvestigationRequest(**common, transcript="Please add S. Iyer as a payee.", audio_authenticity=audio, speaker_verification=None)
    if sid == "I":
        s = session_service.create_session("banking", "id-zira", action.model_dump())
        c = session_service.issue_challenge(s["session_id"])
        session_service.verify_challenge(s["session_id"], c["challenge_id"], c["nonce_for_trusted_channel"])  # legitimate first use
        replay = session_service.verify_challenge(s["session_id"], c["challenge_id"], c["nonce_for_trusted_channel"])  # attacker replays it
        return InvestigationRequest(**common, session_id=s["session_id"], transcript="It's Zira, here's the code again.",
                                    audio_authenticity=audio_fx("real", 0.05), speaker_verification=speaker_fx("match", 0.66), challenge_check=replay)
    if sid == "J":
        ch, _, sess = _valid_banking_checks(action.model_dump())
        approval = session_service.request_approval(sess, action.model_dump(), "Zira's registered phone")
        session_service.decide_approval(approval["approval_id"], True, "Zira's registered phone")
        modified = RequestedAction(type="add_payee", amount=200000, details={"payee": "Unknown account 4481"})
        return InvestigationRequest(**{**common, "requested_action": modified}, session_id=sess, transcript="Actually make it two lakh to account 4481.",
                                    audio_authenticity=audio_fx("real", 0.04), speaker_verification=speaker_fx("match", 0.71), challenge_check=ch,
                                    approval_check=session_service.check_approval(approval["approval_id"], modified.model_dump()))
    # K
    ch, ap, _ = _valid_banking_checks(action.model_dump())
    return InvestigationRequest(**{**common, "speaker_reference_enrolled": False}, transcript="Hi, I've moved house, please update my mailing address.",
                                audio_authenticity=audio_fx("not_sure", 0.47), speaker_verification=None, challenge_check=ch, approval_check=ap)


def run(sid: str, live: bool = False) -> dict:
    exp = SCENARIOS[sid]["expected"]
    rec = orchestrator.run(build(sid, live), expected={"outcome": exp, "description": f"Scenario {sid} should end in {exp}"})
    rec["expected_outcome"] = SCENARIOS[sid]["expected"]
    return rec
