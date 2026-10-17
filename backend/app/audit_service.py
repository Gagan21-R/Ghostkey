"""Append-only, hash-chained audit log: every event links to the previous one, so edits are detectable."""
from __future__ import annotations

import hashlib
import json
import time

from .db import AuditEvent, SessionLocal

GENESIS = "0" * 64


def _hash(body: dict) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def record(event: str, subject: str, payload: dict | None = None) -> dict:
    with SessionLocal() as db:
        last = db.query(AuditEvent).order_by(AuditEvent.seq.desc()).first()
        prev = last.hash if last else GENESIS
        at = time.time()
        body = {"at": at, "event": event, "subject": subject, "payload": payload or {}, "prev_hash": prev}
        row = AuditEvent(at=at, event=event, subject=subject, payload=payload or {}, prev_hash=prev, hash=_hash(body))
        db.add(row)
        db.commit()
        return {"seq": row.seq, "hash": row.hash}


def verify_chain() -> dict:
    with SessionLocal() as db:
        prev = GENESIS
        rows = db.query(AuditEvent).order_by(AuditEvent.seq).all()
        for r in rows:
            body = {"at": r.at, "event": r.event, "subject": r.subject, "payload": r.payload, "prev_hash": r.prev_hash}
            if r.prev_hash != prev or _hash(body) != r.hash:
                return {"ok": False, "broken_at": r.seq, "count": len(rows)}
            prev = r.hash
        return {"ok": True, "count": len(rows), "head": prev}


def recent(limit: int = 200) -> list[dict]:
    with SessionLocal() as db:
        rows = db.query(AuditEvent).order_by(AuditEvent.seq.desc()).limit(limit).all()
        return [{"seq": r.seq, "at": r.at, "event": r.event, "subject": r.subject, "payload": r.payload, "hash": r.hash, "prev_hash": r.prev_hash} for r in rows]
