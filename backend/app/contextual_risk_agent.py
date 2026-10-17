"""Agent 5 — Contextual fraud & action risk: how dangerous is the requested action, and what is missing."""
import re

from .schemas import Challenge, Finding, FindingStatus as F, InvestigationRequest

NAME, VERSION = "contextual_risk_agent", "1.0"
HIGH = {"pin_change", "password_reset", "recovery_change", "account_detail_change", "add_payee", "large_transfer",
        "emergency_transfer", "send_money", "share_otp", "share_password", "share_pin",
        "change_payout_details", "submit_high_value_claim", "change_contact_details", "add_nominee"}
MODERATE = {"start_exam", "continue_exam", "submit_claim"}
PRESSURE = re.compile(r"urgent|immediately|right now|hospital|accident|arrest|don't tell|emergency|quickly|\botp\b|\bpin\b", re.I)


def analyze(req: InvestigationRequest) -> Finding:
    a = req.requested_action
    f = Finding(agent=NAME, agent_version=VERSION, scenario_id=req.scenario_id, finding_type="action_risk", status=F.LOW_RISK_ACTION, kind="hypothesis")
    cues = sorted({m.group(0).lower() for m in PRESSURE.finditer(req.transcript or "")})
    f.observations = [f"Requested action '{a.type}'" + (f" for ₹{a.amount:,.0f}" if a.amount else "") + ".",
                      f"Pressure cues in the transcript: {', '.join(cues) if cues else 'none'}."]
    missing = []
    if req.use_case in ("banking", "insurance") and a.type in HIGH:
        if not (req.challenge_check or {}).get("valid"):
            missing.append("fresh single-use challenge")
        if not (req.approval_check or {}).get("valid"):
            missing.append("trusted-device approval")
    if req.use_case == "family" and (req.independent_verification or {}).get("status") != "passed":
        missing.append("independent verification")
    if a.type in HIGH:
        f.status = F.HIGH_RISK_ACTION
        f.recommended_next_step = "Strongest verification: independent channel plus action-bound approval."
    elif a.type in MODERATE:
        f.status = F.MODERATE_RISK_ACTION
        f.recommended_next_step = "Identity check proportionate to the session."
    else:
        f.recommended_next_step = "Standard verification."
    if missing:
        f.observations.append(f"Missing mandatory evidence: {', '.join(missing)}.")
    f.limitations = ["Pressure cues are risk indicators, not proof of fraud."]
    return f


def respond(f: Finding, ch: Challenge, req: InvestigationRequest) -> Challenge:
    f.disposition = "defended"
    ch.response, ch.outcome = "Defended: sensitivity is a property of the request itself; pressure cues are labelled as indicators only.", "defended"
    return ch
