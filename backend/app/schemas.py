"""Shared structured types. Agents talk to each other only through these (JSON), never free text alone."""
from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class ProviderStatus(str, Enum):
    COMPLETED = "COMPLETED"
    INCONCLUSIVE = "INCONCLUSIVE"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"
    NOT_SUPPORTED = "NOT_SUPPORTED"


class ProviderResult(BaseModel):
    """Normalized provider output. `classification` and `score` are copied from the provider only when it
    returned them; `confidence` stays None because DetectifAI scores are not calibrated probabilities."""
    provider: str = "detectify_ai"
    capability: Literal["audio_authenticity", "speaker_verification", "image_analysis"]
    status: ProviderStatus
    classification: Optional[str] = None  # provider's own label, e.g. "real" | "fake" | "not_sure" | "match"
    confidence: Optional[float] = None
    score: Optional[float] = None  # raw vendor score (semantics in `score_semantics`)
    threshold: Optional[float] = None
    score_semantics: Optional[str] = None
    evidence_summary: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    raw_result_reference: Optional[str] = None  # provider operation_id / request_id
    error: Optional[str] = None
    simulated: bool = False  # True only for labelled demo fixtures — never a real DetectifAI result
    details: dict[str, Any] = Field(default_factory=dict)


class FindingStatus(str, Enum):
    # voice
    SYNTHETIC_INDICATORS = "SYNTHETIC_INDICATORS"
    NO_SYNTHETIC_INDICATORS = "NO_SYNTHETIC_INDICATORS"
    # speaker
    SPEAKER_MATCH_SUPPORTED = "SPEAKER_MATCH_SUPPORTED"
    SPEAKER_MISMATCH_SUSPECTED = "SPEAKER_MISMATCH_SUSPECTED"
    SPEAKER_MATCH_NOT_SUFFICIENT = "SPEAKER_MATCH_NOT_SUFFICIENT"
    NO_REFERENCE = "NO_REFERENCE"
    # exam
    FACE_MATCH_SUPPORTED = "FACE_MATCH_SUPPORTED"
    FACE_MISMATCH_SUSPECTED = "FACE_MISMATCH_SUSPECTED"
    NO_FACE_DETECTED = "NO_FACE_DETECTED"
    MULTIPLE_FACES_DETECTED = "MULTIPLE_FACES_DETECTED"
    LIVENESS_INCONCLUSIVE = "LIVENESS_INCONCLUSIVE"
    REFERENCE_IMAGE_MISSING = "REFERENCE_IMAGE_MISSING"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    # lifecycle
    NUMBER_REASSIGNMENT_SUSPECTED = "NUMBER_REASSIGNMENT_SUSPECTED"
    ACCOUNT_TAKEOVER_SUSPECTED = "ACCOUNT_TAKEOVER_SUSPECTED"
    UNCONFIRMED_REPORT = "UNCONFIRMED_REPORT"
    NO_LIFECYCLE_ANOMALY = "NO_LIFECYCLE_ANOMALY"
    # insurance
    CLAIM_CONSISTENT = "CLAIM_CONSISTENT"
    CLAIM_INCOMPLETE = "CLAIM_INCOMPLETE"
    CLAIM_ANOMALIES_FOUND = "CLAIM_ANOMALIES_FOUND"
    # context
    HIGH_RISK_ACTION = "HIGH_RISK_ACTION"
    MODERATE_RISK_ACTION = "MODERATE_RISK_ACTION"
    LOW_RISK_ACTION = "LOW_RISK_ACTION"
    # generic
    INCONCLUSIVE = "INCONCLUSIVE"
    UNAVAILABLE = "UNAVAILABLE"


class Finding(BaseModel):
    """Agent contract: every agent returns exactly this shape."""
    finding_id: str = Field(default_factory=lambda: new_id("fnd"))
    agent: str
    agent_version: str
    scenario_id: Optional[str] = None
    correlation_id: Optional[str] = None
    created_at: float = Field(default_factory=time.time)
    execution_status: Literal["completed", "failed", "timeout", "skipped"] = "completed"
    evidence_source: Literal["live_provider", "simulated_fixture", "local_face_model", "structured_case_data", "session_service", "none"] = "none"
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    finding_type: str
    status: FindingStatus
    confidence: Optional[float] = None
    evidence_refs: list[str] = Field(default_factory=list)
    observations: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    recommended_next_step: Optional[str] = None
    kind: Literal["observed_fact", "model_prediction", "hypothesis"] = "model_prediction"
    revision: int = 0
    disposition: Literal["active", "defended", "revised", "retracted"] = "active"
    history: list[dict[str, Any]] = Field(default_factory=list)


class Challenge(BaseModel):
    challenge_id: str = Field(default_factory=lambda: new_id("chl"))
    round: int
    target_finding_id: str
    target_agent: str
    question: str
    kind: str
    response: Optional[str] = None
    outcome: Optional[Literal["defended", "revised", "retracted", "unresolved"]] = None


class RequestedAction(BaseModel):
    type: str
    amount: Optional[float] = None
    details: dict[str, Any] = Field(default_factory=dict)


class FaceFrame(BaseModel):
    """One analysed webcam frame (from the real OpenCV model, or a labelled fixture)."""
    frame_index: int
    captured_at: float
    faces: int
    best_similarity: Optional[float] = None
    detection_score: Optional[float] = None
    brightness: Optional[float] = None
    frame_hash: Optional[str] = None
    simulated: bool = False


class InvestigationRequest(BaseModel):
    use_case: Literal["family", "exam", "banking", "insurance"]
    correlation_id: str = Field(default_factory=lambda: new_id("cor"))
    scenario_id: Optional[str] = None
    title: Optional[str] = None
    identity_id: Optional[str] = None
    claimed_identity: Optional[str] = None
    actor_role: str = "customer"
    requested_action: RequestedAction
    transcript: Optional[str] = None
    audio_authenticity: Optional[ProviderResult] = None
    speaker_verification: Optional[ProviderResult] = None
    speaker_reference_enrolled: bool = False
    face_frames: list[FaceFrame] = Field(default_factory=list)
    face_reference_enrolled: bool = False
    face_model: Optional[dict[str, Any]] = None
    carrier_events: list[dict[str, Any]] = Field(default_factory=list)
    account_events: list[dict[str, Any]] = Field(default_factory=list)
    session_id: Optional[str] = None
    challenge_check: Optional[dict[str, Any]] = None  # result from session_service.verify_challenge
    approval_check: Optional[dict[str, Any]] = None  # result from session_service.check_approval
    independent_verification: Optional[dict[str, Any]] = None  # e.g. {"method": "callback_to_recovery_number", "status": "passed"}
    claim: Optional[dict[str, Any]] = None  # SYNTHETIC insurance demo record
    policyholder: Optional[dict[str, Any]] = None  # SYNTHETIC
    force_disagreement: bool = False


class PolicyOutcome(str, Enum):
    VERIFIED_AND_AUTHORIZED = "VERIFIED_AND_AUTHORIZED"
    HOLD_FOR_VERIFICATION = "HOLD_FOR_VERIFICATION"
    DENIED = "DENIED"
    ESCALATED_FOR_REVIEW = "ESCALATED_FOR_REVIEW"


class Requirement(BaseModel):
    name: str
    satisfied: bool
    detail: str


class PolicyDecision(BaseModel):
    outcome: PolicyOutcome
    profile: str
    reasons: list[str]
    requirements: list[Requirement]
    rules_fired: list[str] = Field(default_factory=list)
    headline: str = ""  # one short reason for the result screen, generated from the actual decision
    decided_at: float = Field(default_factory=time.time)
