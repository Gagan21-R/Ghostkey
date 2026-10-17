"""Verification sessions, single-use challenges and action-bound trusted-device approvals.

- A challenge is a random nonce shown on the user's enrolled trusted channel; only its hash is stored.
  It expires after CHALLENGE_TTL seconds and can be used once (replays are rejected and audited).
- An approval is bound to the SHA-256 of the exact requested action. If the action changes, the old
  approval no longer matches and is invalid (rule 8).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from typing import Optional

from . import audit_service
from .db import Approval, ChallengeRow, SessionLocal, VerificationSession
from .schemas import new_id

SESSION_TTL = 15 * 60
CHALLENGE_TTL = 120


def _normalize(v):
    """84000 and 84000.0 are the same amount; None and missing keys are dropped so equal actions hash equally."""
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, dict):
        return {k: _normalize(x) for k, x in v.items() if x is not None}
    if isinstance(v, list):
        return [_normalize(x) for x in v]
    return v


def action_hash(action: dict) -> str:
    return hashlib.sha256(json.dumps(_normalize(action), sort_keys=True, default=str).encode()).hexdigest()


def _h(nonce: str) -> str:
    return hashlib.sha256(nonce.encode()).hexdigest()


def create_session(use_case: str, identity_id: Optional[str], action: dict) -> dict:
    now = time.time()
    with SessionLocal() as db:
        s = VerificationSession(id=new_id("ses"), use_case=use_case, identity_id=identity_id or "", action=action,
                                action_hash=action_hash(action), created_at=now, expires_at=now + SESSION_TTL)
        db.add(s)
        db.commit()
    audit_service.record("session.created", s.id, {"use_case": use_case, "action": action})
    return {"session_id": s.id, "action_hash": s.action_hash, "expires_at": s.expires_at}


def issue_challenge(session_id: str) -> dict:
    """Returns the nonce once (to be delivered over the trusted channel); only its hash is stored."""
    nonce = f"{secrets.randbelow(10**6):06d}"
    now = time.time()
    with SessionLocal() as db:
        c = ChallengeRow(id=new_id("cha"), session_id=session_id, nonce_hash=_h(nonce), issued_at=now, expires_at=now + CHALLENGE_TTL)
        db.add(c)
        db.commit()
    audit_service.record("challenge.issued", session_id, {"challenge_id": c.id})
    return {"challenge_id": c.id, "nonce_for_trusted_channel": nonce, "expires_at": c.expires_at}


def verify_challenge(session_id: str, challenge_id: str, response: str, now: Optional[float] = None) -> dict:
    now = now or time.time()
    with SessionLocal() as db:
        c = db.get(ChallengeRow, challenge_id)
        s = db.get(VerificationSession, session_id)
        if not c or not s or c.session_id != session_id:
            result = {"valid": False, "reason": "unknown_challenge"}
        elif c.used_at is not None:
            result = {"valid": False, "reason": "replayed_challenge", "first_used_at": c.used_at}
        elif now > c.expires_at:
            result = {"valid": False, "reason": "expired_challenge"}
        elif now > s.expires_at:
            result = {"valid": False, "reason": "expired_session"}
        elif not hmac.compare_digest(c.nonce_hash, _h(response)):
            c.used_at = now  # a wrong answer also burns the challenge
            db.commit()
            result = {"valid": False, "reason": "wrong_response"}
        else:
            c.used_at = now
            db.commit()
            result = {"valid": True, "reason": "fresh_single_use_challenge_passed", "challenge_id": challenge_id}
    audit_service.record("challenge.verified" if result["valid"] else "challenge.rejected", session_id, result)
    return result


def request_approval(session_id: str, action: dict, device: str) -> dict:
    with SessionLocal() as db:
        a = Approval(id=new_id("apr"), session_id=session_id, action_hash=action_hash(action), action=action, device=device)
        db.add(a)
        db.commit()
    audit_service.record("approval.requested", session_id, {"approval_id": a.id, "device": device, "action": action})
    return {"approval_id": a.id, "action_hash": a.action_hash, "shown_on_device": action}


def decide_approval(approval_id: str, approve: bool, device: str) -> dict:
    with SessionLocal() as db:
        a = db.get(Approval, approval_id)
        if not a:
            return {"ok": False, "reason": "unknown_approval"}
        if a.device != device:
            return {"ok": False, "reason": "approval_from_untrusted_device"}
        a.status = "approved" if approve else "rejected"
        a.decided_at = time.time()
        db.commit()
    audit_service.record("approval." + a.status, a.session_id, {"approval_id": approval_id, "device": device})
    return {"ok": True, "status": a.status}


def check_approval(approval_id: Optional[str], current_action: dict) -> dict:
    if not approval_id:
        return {"valid": False, "reason": "no_approval"}
    with SessionLocal() as db:
        a = db.get(Approval, approval_id)
        if not a:
            return {"valid": False, "reason": "unknown_approval"}
        if a.status != "approved":
            return {"valid": False, "reason": f"approval_{a.status}"}
        if a.action_hash != action_hash(current_action):
            audit_service.record("approval.invalidated", a.session_id, {"approval_id": approval_id, "reason": "action_changed_after_approval"})
            return {"valid": False, "reason": "action_changed_after_approval", "approved_action": a.action, "current_action": current_action}
        return {"valid": True, "reason": "approved_on_trusted_device_for_this_exact_action", "device": a.device}
