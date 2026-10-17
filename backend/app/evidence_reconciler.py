"""Agent 7 — Evidence Reconciliation. Builds the claim graph: who claimed what, on which evidence,
who challenged it, and whether it was defended, revised or retracted. Never invents consensus."""
from .schemas import Challenge, Finding

NAME, VERSION = "evidence_reconciler", "1.0"


def reconcile(original: list[dict], findings: list[Finding], challenges: list[Challenge], unresolved: list[str], provider_facts: list[dict]) -> dict:
    orig = {o["finding_id"]: o for o in original}
    claims = []
    for f in findings:
        before = orig.get(f.finding_id, {})
        cs = [c for c in challenges if c.target_finding_id == f.finding_id]
        claims.append({
            "claim_id": f.finding_id,
            "agent": f.agent,
            "claim": f.status.value,
            "original_claim": before.get("status"),
            "changed": before.get("status") != f.status.value or f.revision > 0,
            "kind": f.kind,
            "evidence": f.evidence_refs,
            "challenged_by": ["adversarial_critic"] if cs else [],
            "challenges": [{"question": c.question, "response": c.response, "outcome": c.outcome} for c in cs],
            "disposition": f.disposition if cs else "unchallenged",
        })
    return {
        "agent": NAME,
        "version": VERSION,
        "claims": claims,
        "changed_after_challenge": [c["claim_id"] for c in claims if c["changed"]],
        "disagreements": unresolved,
        "observed_facts": provider_facts + [{"source": f.agent, "fact": o} for f in findings if f.kind == "observed_fact" for o in f.observations],
        "model_predictions": [{"source": f.agent, "status": f.status.value} for f in findings if f.kind == "model_prediction"],
        "hypotheses": [{"source": f.agent, "status": f.status.value, "note": f.recommended_next_step} for f in findings if f.kind == "hypothesis"],
        "consensus": "none claimed" if unresolved else "no unresolved contradictions",
    }
