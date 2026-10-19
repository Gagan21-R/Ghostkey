"""SQLite persistence (SQLAlchemy). Biometric minimisation: face references are stored only as
embeddings with a consent flag; raw reference images and audio are not kept."""
from __future__ import annotations

import json
import os
import time

from sqlalchemy import JSON, Boolean, Column, Float, Integer, String, Text, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

DEFAULT_DB = "sqlite:///./ghostkey.db"


def _database_url(raw: str | None) -> str:
    """Accept the forms people actually paste into hosting dashboards: surrounding quotes or spaces,
    a plain file path ("/data/ghostkey.db"), or "sqlite:/" typos. An unusable value falls back to the
    default with a clear log line instead of crashing the backend at import time."""
    url = (raw or "").strip().strip("'\"").strip()
    if not url:
        return DEFAULT_DB
    if "://" not in url:  # plain path → SQLite file, but only if it looks like one
        if not url.lower().endswith((".db", ".sqlite", ".sqlite3")) or any(c in url for c in "${} "):
            print(f"[ghostkey] WARNING: GHOSTKEY_DB is not a database URL or .db path ({url[:60]!r}); using {DEFAULT_DB}", flush=True)
            return DEFAULT_DB
        url = "sqlite:///" + url
    try:
        make_url(url)
        return url
    except Exception:
        print(f"[ghostkey] WARNING: GHOSTKEY_DB is not a valid database URL ({url[:60]!r}); using {DEFAULT_DB}", flush=True)
        return DEFAULT_DB


DB_URL = _database_url(os.getenv("GHOSTKEY_DB"))
if DB_URL.startswith("sqlite:///"):
    # create the database's folder if needed (e.g. a fresh /data volume, or a relative "data/..." path)
    _db_dir = os.path.dirname(os.path.abspath(DB_URL[len("sqlite:///"):]))
    os.makedirs(_db_dir, exist_ok=True)
print(f"[ghostkey] database: {DB_URL.split('?')[0]}", flush=True)
engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    name = Column(String)
    role = Column(String)  # customer | support_agent | student | proctor | family_member | admin


class Identity(Base):
    __tablename__ = "identities"
    id = Column(String, primary_key=True)
    name = Column(String)
    use_case = Column(String)
    phone = Column(String, default="")
    recovery_method = Column(String, default="")
    speaker_id = Column(String, default="")  # DetectifAI speaker_id once enrolled
    speaker_enrolled = Column(Boolean, default=False)
    face_embedding = Column(JSON, nullable=True)  # 128-d SFace embedding, no image stored
    face_consent = Column(Boolean, default=False)
    trusted_device = Column(String, default="")
    created_at = Column(Float, default=time.time)


class TrustedContact(Base):
    __tablename__ = "trusted_contacts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    identity_id = Column(String)
    name = Column(String)
    relation = Column(String)
    phone = Column(String)


class VerificationSession(Base):
    __tablename__ = "verification_sessions"
    id = Column(String, primary_key=True)
    use_case = Column(String)
    identity_id = Column(String)
    action = Column(JSON)
    action_hash = Column(String)
    created_at = Column(Float, default=time.time)
    expires_at = Column(Float)
    status = Column(String, default="open")


class ChallengeRow(Base):
    __tablename__ = "challenges"
    id = Column(String, primary_key=True)
    session_id = Column(String)
    nonce_hash = Column(String)
    issued_at = Column(Float)
    expires_at = Column(Float)
    used_at = Column(Float, nullable=True)


class Approval(Base):
    __tablename__ = "approvals"
    id = Column(String, primary_key=True)
    session_id = Column(String)
    action_hash = Column(String)
    action = Column(JSON)
    device = Column(String)
    status = Column(String, default="pending")  # pending | approved | rejected
    decided_at = Column(Float, nullable=True)


class ProviderResultRow(Base):
    __tablename__ = "provider_results"
    id = Column(Integer, primary_key=True, autoincrement=True)
    investigation_id = Column(String)
    capability = Column(String)
    status = Column(String)
    simulated = Column(Boolean)
    payload = Column(JSON)


class FaceResultRow(Base):
    __tablename__ = "face_results"
    id = Column(Integer, primary_key=True, autoincrement=True)
    investigation_id = Column(String)
    payload = Column(JSON)


class FindingRow(Base):
    __tablename__ = "agent_findings"
    id = Column(String, primary_key=True)
    investigation_id = Column(String)
    agent = Column(String)
    status = Column(String)
    disposition = Column(String)
    payload = Column(JSON)


class DecisionRow(Base):
    __tablename__ = "policy_decisions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    investigation_id = Column(String)
    outcome = Column(String)
    payload = Column(JSON)


class Investigation(Base):
    __tablename__ = "investigations"
    id = Column(String, primary_key=True)
    use_case = Column(String)
    scenario_id = Column(String, nullable=True)
    title = Column(String)
    outcome = Column(String)
    created_at = Column(Float, default=time.time)
    record = Column(Text)  # full JSON record (timeline, findings, challenges, claim graph, decision)

    def to_dict(self) -> dict:
        return json.loads(self.record)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    seq = Column(Integer, primary_key=True, autoincrement=True)
    at = Column(Float)
    event = Column(String)
    subject = Column(String)
    payload = Column(JSON)
    prev_hash = Column(String)
    hash = Column(String)


def init_db() -> None:
    Base.metadata.create_all(engine)


class TestReport(Base):
    """One persistent report per test execution (created RUNNING, updated as it progresses, never dropped on failure)."""
    __tablename__ = "test_reports"
    __test__ = False  # not a pytest class
    id = Column(String, primary_key=True)
    category = Column(String, index=True)
    name = Column(String)
    feature = Column(String, index=True)
    status = Column(String, index=True)  # RUNNING | PASS | FAIL | HOLD | ERROR | SKIPPED
    execution_status = Column(String)  # running | completed | error | incomplete
    verification_outcome = Column(String, nullable=True)
    case_id = Column(String, nullable=True, index=True)
    correlation_id = Column(String, nullable=True)
    speaker_id = Column(String, nullable=True, index=True)
    provider = Column(String, nullable=True)
    created_at = Column(Float, default=time.time, index=True)
    finished_at = Column(Float, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    payload = Column(Text)  # full sanitized report JSON
