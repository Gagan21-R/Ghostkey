"""Agent 4 — SIM & account-lifecycle risk. Works only on clearly labelled SIMULATED carrier events;
GhostKey has no telecom-carrier integration and never claims to detect SIM swaps directly."""
from .schemas import Challenge, Finding, FindingStatus as F, InvestigationRequest

NAME, VERSION = "sim_risk_agent", "1.0"


def analyze(req: InvestigationRequest) -> Finding:
    f = Finding(agent=NAME, agent_version=VERSION, scenario_id=req.scenario_id, finding_type="number_lifecycle", status=F.NO_LIFECYCLE_ANOMALY)
    ev, acct = req.carrier_events, req.account_events
    f.evidence_refs = [f"carrier_event:{e.get('type')} [SIMULATED]" for e in ev] + [f"account_event:{e.get('type')}" for e in acct]
    f.limitations = ["Carrier events are synthetic demo data — no telecom carrier was contacted.", "A familiar number is never treated as proof of identity."]
    types = {e.get("type") for e in ev}
    recovery_changed = any(e.get("type") == "recovery_channel_changed" for e in acct)
    unconfirmed = any(e.get("confirmed") is False for e in ev)
    if "sim_swap_alert" in types or recovery_changed:
        f.status = F.ACCOUNT_TAKEOVER_SUSPECTED
        f.observations = ["SIM-swap alert or recent recovery-channel change on the protected number (simulated event)."]
        f.recommended_next_step = "Verify through the independent recovery method, not through the number."
    elif "number_reassigned" in types:
        f.status = F.UNCONFIRMED_REPORT if unconfirmed else F.NUMBER_REASSIGNMENT_SUSPECTED
        f.observations = ["The protected number was deactivated and reassigned" + (" — unconfirmed report." if unconfirmed else " (simulated carrier event).")]
        f.recommended_next_step = "Whoever holds this number now may be a new owner; require independent verification."
    else:
        f.observations = ["No lifecycle anomaly in the available (simulated) events."]
        f.recommended_next_step = "Number history looks normal, but it still does not establish identity."
    f.kind = "observed_fact" if ev or acct else "hypothesis"
    return f


def respond(f: Finding, ch: Challenge, req: InvestigationRequest) -> Challenge:
    if ch.kind == "benign_explanation":
        f.limitations.append("Revised after critic: a real relative who changed numbers looks the same; only independent verification separates the two.")
        f.revision += 1
        f.disposition = "revised"
        ch.response, ch.outcome = "Revised: number reassignment is a risk factor, not proof of impersonation. Recommend independent verification.", "revised"
    else:
        ch.response, ch.outcome = "Defended: events are labelled simulated and describe the number, not the caller.", "defended"
    return ch
