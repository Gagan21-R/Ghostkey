# GHOSTKEY 2.0 — Architecture

## Data flow

```
Browser (Next.js 15 / React / Tailwind)
   │  /api/*  (no secrets in the browser)
   ▼
Next.js route proxy  ── adds X-GhostKey-Token (server env) ──▶  FastAPI (Python)
                                                                  │
   upload validation (file_validation.py: type, size, WAV duration; files kept in memory only)
                                                                  │
   ┌───────────── provider evidence ─────────────┐               │
   │ detectify_provider.py → DetectifAI REST API │  face_service.py → OpenCV YuNet + SFace (local)
   │   POST /v1/deepfake/detect                  │
   │   POST /v1/speakers/verify  (+deepfake)     │  session_service.py → sessions, single-use
   │   POST /v1/speakers/enroll, DELETE speaker  │     challenges, action-bound approvals
   │   GET  /v1/health, /v1/credits              │
   └─────────────────────────────────────────────┘
                                                                  │
   orchestrator.py  (case_id + correlation_id per workflow)
     1. specialists in parallel, 10 s timeout each, crashes recorded as failed (never a pass)
     2. shared evidence store (structured Finding JSON)
     3. adversarial_critic → challenges → agents defend / revise / retract (max 2 rounds)
     4. evidence_reconciler → claim graph, disagreements kept visible
     5. policy_engine → VERIFIED_AND_AUTHORIZED | HOLD_FOR_VERIFICATION | DENIED | ESCALATED_FOR_REVIEW
     6. audit_service → SHA-256 hash-chained audit log
                                                                  │
   SQLite via SQLAlchemy: identities, trusted contacts, sessions, challenges, approvals,
   provider results, face results, findings, decisions, investigations, audit events
```

**Database choice:** the spec prefers MongoDB "if configured". It is not configured in this environment,
so the working SQLite/SQLAlchemy layer is retained (zero setup, file-based, easy to wipe). Records are stored
as typed rows plus the full case JSON, so moving to MongoDB is a repository swap.

**Face library choice:** OpenCV's YuNet detector + SFace recognizer (ONNX, Apache-2.0, runs on CPU) instead of
DeepFace, which needs TensorFlow and was not compatible/needed here. Threshold 0.363 cosine is OpenCV's
published value; the exam page allows 0.2–0.7.

## Agents (all rule-based Python modules — no LLM)

| Agent | Module | Input | Output finding_type |
| --- | --- | --- | --- |
| Voice Authenticity | `voice_authenticity_agent.py` | DetectifAI deepfake result | `voice_authenticity` |
| Speaker Identity | `speaker_identity_agent.py` | DetectifAI speaker verification + enrollment state | `speaker_identity` |
| Exam Face | `exam_identity_agent.py` | per-frame OpenCV outputs, reference embedding | `exam_identity` |
| Contextual Risk | `contextual_risk_agent.py` | requested action, transcript cues, missing evidence | `action_risk` |
| SIM / Account Risk | `sim_risk_agent.py` | SIMULATED carrier + account events | `number_lifecycle` |
| Insurance Claim | `insurance_claim_agent.py` | SYNTHETIC claim + policyholder record | `claim_consistency` |
| Adversarial Critic | `adversarial_critic.py` | all findings | challenges + unresolved issues |
| Evidence Reconciler | `evidence_reconciler.py` | original + revised findings, challenges | claim graph, facts vs predictions vs hypotheses |
| Policy Engine | `policy_engine.py` | request + findings + unresolved issues | `PolicyDecision` |

**Agent contract** (`schemas.Finding`): finding_id, agent, agent_version, scenario_id, correlation_id,
created_at, execution_status (completed/failed/timeout/skipped), evidence_source (live_provider /
simulated_fixture / local_face_model / structured_case_data / session_service / none), status,
confidence (always null unless legitimately computed — vendor scores are not calibrated probabilities),
observations, evidence_refs, limitations, contradictions, warnings, errors, recommended_next_step, kind
(observed_fact / model_prediction / hypothesis), revision, disposition, history.

## Security decisions (policy_engine.py)

| Rule | Effect |
| --- | --- |
| R1 | An unavailable/failed detector is never a successful detection; during a mandatory voice check → HOLD |
| R2 | Missing authentication evidence is never a pass → HOLD |
| R3 | A voice result alone never authorizes payments, payout changes, account recovery or other sensitive actions |
| R4 | Face similarity never proves liveness; single-image matches cannot start an exam |
| R5 | A phone number never establishes identity |
| R6 | Stale, expired or replayed challenges are rejected (replay → DENIED) |
| R7 | Roles outside the profile's permissions → DENIED |
| R8 | Approvals are bound to the SHA-256 of the exact action; any change invalidates them |
| R9 | Conflicting or inconclusive evidence after authentication → ESCALATED_FOR_REVIEW |
| R10/R11 | Suspicion is not proof; exam and claim anomalies go to human review, never an automatic accusation |
| R12 | No number of agent findings can override a mandatory requirement |
| Forbidden | Requests to share OTPs, PINs or passwords are always DENIED |

Profiles: **family** (independent verification over an enrolled recovery channel), **exam** (multi-frame
face match, one person, human review), **insurance** (documents + challenge + simulated trusted-device
approval bound to claim and action; mandatory voice check when a voiceprint is on file), **banking**
(challenge + approval for sensitive changes).

## Privacy
- Uploaded audio and images are processed in memory and never written to disk.
- Face references are stored only as 128-d embeddings with a consent flag; `DELETE /api/identities/{id}/face` removes them and related face results.
- Cases auto-purge after `GHOSTKEY_CASE_RETENTION_DAYS`; `DELETE /api/investigations/{id}` removes a case (an audit event records the deletion).
- Secrets live in `backend/.env`; the browser only talks to the Next.js proxy.
