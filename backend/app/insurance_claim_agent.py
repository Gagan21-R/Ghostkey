"""Insurance Claim Agent — inspects structured (SYNTHETIC) claim data for inconsistencies and missing evidence.
Each anomaly is a risk indicator for review, never an accusation of fraud."""
from datetime import date

from .insurance_data import PRIOR_CLAIM_REFS
from .schemas import Challenge, Finding, FindingStatus as F, InvestigationRequest

NAME, VERSION = "insurance_claim_agent", "1.0"
HIGH_VALUE = 300000


def _d(s):
    return date.fromisoformat(s) if s else None


def analyze(req: InvestigationRequest) -> Finding:
    c, ph = req.claim or {}, req.policyholder or {}
    f = Finding(agent=NAME, agent_version=VERSION, scenario_id=req.scenario_id, finding_type="claim_consistency", status=F.CLAIM_CONSISTENT,
                kind="observed_fact", evidence_source="structured_case_data")
    if not c:
        f.status, f.execution_status = F.UNAVAILABLE, "skipped"
        f.observations = ["No claim record supplied."]
        return f
    f.evidence_refs = [f"claim:{c['claim_id']} [SYNTHETIC]", f"policy:{ph.get('policy_ref')} [SYNTHETIC]"]
    f.limitations = ["Synthetic demo records only.", "Anomalies are indicators for review, not evidence of fraud."]
    missing = sorted(set(c.get("required_documents", [])) - set(c.get("documents", [])))
    anomalies = []
    if c.get("duplicate_of") and c["duplicate_of"] in PRIOR_CLAIM_REFS:
        anomalies.append(f"References an earlier claim {c['duplicate_of']} for a similar event (possible duplicate).")
    if c.get("new_payout_account"):
        anomalies.append(f"Requests a payout account change to {c['new_payout_account']} during an open claim.")
    if ph.get("payout_account_changed_at"):
        anomalies.append(f"Payout account was already changed on {ph['payout_account_changed_at']}.")
    start, incident, reported = _d(ph.get("policy_start")), _d(c.get("incident_date")), _d(c.get("reported_date"))
    if start and incident and (incident - start).days < 0:
        anomalies.append("Incident date is before the policy start date.")
    elif start and incident and (incident - start).days < 30:
        anomalies.append(f"Incident occurred only {(incident - start).days} days after the policy started.")
    if incident and reported and (reported - incident).days > 14:
        anomalies.append(f"Reported {(reported - incident).days} days after the incident.")
    if c.get("amount", 0) > ph.get("sum_insured", float("inf")):
        anomalies.append("Claimed amount exceeds the sum insured.")
    if c.get("claimant_relation") != "self" and not any(c["claimant"].split()[0] in r for r in ph.get("authorized_representatives", [])):
        anomalies.append("Claimant is not a listed authorized representative.")
    f.observations = [f"{c['claim_type']} claim of ₹{c['amount']:,} on {c['policy_ref'] if 'policy_ref' in c else ph.get('policy_ref')}; requested action '{c['requested_action']}'.",
                      f"Documents present: {', '.join(c.get('documents', [])) or 'none'}; missing: {', '.join(missing) or 'none'}."] + anomalies
    if c.get("amount", 0) >= HIGH_VALUE:
        f.warnings.append(f"High-value claim (≥ ₹{HIGH_VALUE:,}).")
    if anomalies:
        f.status = F.CLAIM_ANOMALIES_FOUND
        f.recommended_next_step = "Independent verification with the policyholder on the registered channel, then claims-officer review."
    elif missing:
        f.status = F.CLAIM_INCOMPLETE
        f.recommended_next_step = f"Request missing documents: {', '.join(missing)}."
    else:
        f.recommended_next_step = "Claim data is consistent; standard processing with identity verification."
    f.contradictions = []
    return f


def respond(f: Finding, ch: Challenge, req: InvestigationRequest) -> Challenge:
    if ch.kind == "benign_explanation":
        f.limitations.append("Revised after critic: late reporting or a new account can be legitimate (hospital stay, bank change); review, do not reject.")
        f.revision += 1
        f.disposition = "revised"
        ch.response, ch.outcome = "Revised: each anomaly has possible legitimate explanations; recommending review and verification, not rejection.", "revised"
    else:
        f.disposition = "defended"
        ch.response, ch.outcome = "Defended: findings are direct reads of the claim record and are labelled as indicators.", "defended"
    return ch
