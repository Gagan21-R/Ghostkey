# GHOSTKEY 2.0 — multi-agent identity defense

**Central outcome:** a convincing voice or face impersonation is never enough to gain trust or authorize a
sensitive action. Seven agents investigate, an adversarial critic challenges them, and a deterministic
policy engine (not an AI) decides: `VERIFIED_AND_AUTHORIZED`, `HOLD_FOR_VERIFICATION`, `DENIED` or `ESCALATED_FOR_REVIEW`.

Use cases: **family & SIM impersonation**, **online exam impersonation**, **insurance claim impersonation**
(synthetic records), plus a **banking** module. See [ARCHITECTURE.md](ARCHITECTURE.md), [TESTING_GUIDE.md](TESTING_GUIDE.md) and [IMPLEMENTATION_REPORT.md](IMPLEMENTATION_REPORT.md) (speaker-verification root cause, test reporting, test results).

Pages: dashboard & 17 scenarios · family/SIM · exam · insurance claims · banking · voice analysis (upload or
record) · speaker enrollment & verification · case history (with deletion) · audit trail · settings.

## Real-human examples & explainer

- **Exam:** 11 students built from real photos in Caltech Faces 1999 (MIT licence), grouped by person with the face model; match, substitute, poor light, two people, photo replay, looking away, single photo. Run free (local model).
- **Family & SIM:** 10 real callers from MINDS-14 (CC BY 4.0) + 2 labelled AI voices; the family context is synthetic.
- **Insurance:** 10 real callers from MINDS-14 + 2 labelled AI voices; claims are synthetic.
- "Run" skips the voice check (reported as missing evidence); "Analyse with DetectifAI" spends 1 check and uses the live result.
- **Explain chatbot:** the floating guide and every "Explain" button use a built-in knowledge base that also reads the result on screen (offline, no API key).
- Rebuild examples: `backend/.venv/Scripts/python backend/scripts/build_face_examples.py datasets/raw examples/exam` and `py -E -P backend/scripts/build_voice_examples.py examples` (run from `backend/`).

## Judges: test it yourself
Every voice use case (Family & SIM, Insurance, Banking) has a **Test it yourself** tab: pick a situation, **add yourself (or anyone) to the database** as the caller / customer / policyholder, optionally enroll a **3-second voiceprint**, then record or pick the audio to test (e.g. an AI clone) and run. It is always a live DetectifAI call (1 check, 2 with a voiceprint). People you add stay in SQLite until deleted (delete also removes their DetectifAI voiceprint). Exam has **Test yourself (webcam)**: add yourself as a student, enroll your face with consent, verify with live frames.

- **3-second enrollment:** DetectifAI's enroll endpoint needs 15–60 s, so a 3–15 s sample is repeated up to 16 s on the backend and the result says so. Live check: enrolled from 3.2 s of a MINDS-14 caller → same caller *match* (0.63 vs 0.53), different caller *no_match* (0.15).
- **Audio picker:** record, drag-and-drop, or pick from **Latest in Downloads** (refreshed every 4 s, newest first; a file downloaded while the page is open is selected automatically). MP4/3GP audio (WhatsApp "Audio" files) is converted to WAV in the browser, or forwarded to DetectifAI as M4A.
- **Face & voice cards** use an adapted *Momentum Rail* from [Kokonut UI](https://kokonutui.com) (MIT): drag/flick, spring snapping, cover-flow depth and parallax; a grid view is one click away.

## Test reports
Every test (deepfake check, enrollment, speaker verification, every investigation, connectivity, the pytest suite, the frontend smoke test) creates a persistent report: **Test reports** in the sidebar, or `GET /api/reports`. Each result screen has a **View test report** button; reports export as JSON and print as PDF.

## Run it (Windows)

```bash
# backend
cd ghostkey/backend
py -m venv .venv
.venv/Scripts/python -m pip install fastapi "uvicorn[standard]" sqlalchemy pydantic httpx python-multipart opencv-python-headless numpy pytest python-dotenv
copy .env.example .env                       # set DETECTIF_API_KEY
.venv/Scripts/python -m pytest -q            # 90 tests (+1 live test, opt-in), no live AI needed

# frontend (+ backend together)
cd ../frontend
npm install
copy .env.example .env.local
npm run dev:all                               # FastAPI :8000 + Next.js :3000 → open http://localhost:3000 in Chrome
```

Face models (in `backend/models/`, from [opencv_zoo](https://github.com/opencv/opencv_zoo), Apache-2.0):
`face_detection_yunet_2023mar.onnx`, `face_recognition_sface_2021dec.onnx`.

### Environment variables
| Where | Variable | Purpose |
| --- | --- | --- |
| backend/.env | `DETECTIF_API_KEY` (or `DETECTIFAI_API_KEY`) | DetectifAI key (server-side only) |
| backend/.env | `GHOSTKEY_MAX_AUDIO_MB`, `GHOSTKEY_MAX_IMAGE_MB`, `GHOSTKEY_CASE_RETENTION_DAYS`, `GHOSTKEY_DB` | upload limits, case retention, database URL |
| backend/.env | `DETECTIFAI_BASE_URL` | default `https://platform.detectif.ai` |
| backend/.env | `GHOSTKEY_API_TOKEN` | internal token required on every `/api` route except `/api/health` |
| backend/.env | `GHOSTKEY_LOCAL_DOWNLOADS`, `GHOSTKEY_DOWNLOADS_DIR` | "Latest in Downloads" picker (default on, `~/Downloads`). **Set `GHOSTKEY_LOCAL_DOWNLOADS=0` before sharing a public link** — otherwise visitors can list/download audio files from the host's Downloads folder |
| backend/.env | `GHOSTKEY_DEMO_SPEAKER_ID` | DetectifAI speaker used by live scenario E (default `cust-zira-rao-7d3e`) |
| frontend/.env.local | `BACKEND_URL`, `GHOSTKEY_API_TOKEN` | the Next.js server proxy adds the token; the browser never sees it |

## Architecture

```
Browser (Next.js pages) ──/api/*──▶ Next.js route proxy (adds internal token)
                                        │
                                        ▼
FastAPI ── input validation ── detectify_provider (DetectifAI: deepfake detect, speaker verify/enroll)
   │                          └ face_service (OpenCV YuNet + SFace, real model)
   ├── session_service: sessions · single-use 2-min challenges (hash only) · action-bound trusted-device approvals
   ├── orchestrator.py:
   │     parallel specialists → shared evidence store → adversarial_critic (≤2 rounds)
   │       voice_authenticity_agent   speaker_identity_agent   exam_identity_agent
   │       sim_risk_agent             contextual_risk_agent
   │     → agents defend / revise / retract → evidence_reconciler (claim graph, disagreements kept visible)
   │     → policy_engine (deterministic profiles: family · exam · banking; rules R1–R12)
   └── audit_service: SHA-256 hash-chained audit log · SQLite (SQLAlchemy) for all records
```

## Real vs simulated

| Real | Simulated (always labelled) |
| --- | --- |
| DetectifAI deepfake detection, speaker verification, enrollment (live API calls) | Provider results in scenarios A–D, F, G, I–Q (`simulated: true`, "SIMULATED fixture") |
| OpenCV face detection + SFace face matching on webcam/uploaded frames | Face-frame outputs in scenarios C and D |
| Sessions, single-use challenges, replay detection, action-bound approvals (scenarios I and J run the real code) | Carrier events: number reassignment, SIM-swap alerts (no telecom integration) |
| Policy engine, critic, reconciler, audit chain | Trusted device and recovery channel (shown on screen instead of a phone/email) |
| Provider failure path (scenario H calls an unreachable host) | Insurance policyholders and claims (all synthetic, labelled) |

**Not built:** n8n (the same workflow runs in FastAPI), LLM agents (agents are deterministic and versioned;
no LLM key was available), a presentation-attack/liveness model (results always say liveness is unproven),
DetectifAI image analysis (not in their documented API → `NOT_SUPPORTED`).

## Provider limitations (from DetectifAI's docs)
Results are signals, not proof · phone-quality audio and voice notes are less reliable · the deepfake check
is tuned for English · deepfake needs > 4 s of audio · speaker verification needs an enrolled speaker
(15–60 s enrollment) · scores are vendor scores, not calibrated probabilities (GhostKey keeps `confidence: null`).

## Demo script (≈4 min)
1. **Dashboard → Integration status:** DetectifAI reachable, key on backend, face model loaded, honest n8n/LLM status.
2. **Scenario E with "live DetectifAI" ticked:** real DetectifAI flags the cloned audio synthetic while the
   voiceprint matches → the critic asks "could a clone pass speaker verification?" → the speaker agent revises
   → disagreement stays visible → policy **HOLDS** the PIN change: no challenge, no device approval.
3. **Scenario A vs B:** same reassigned number; A fails independent verification → HOLD; B passes → AUTHORIZED.
4. **Scenarios I and J:** replayed code → DENIED; approval reused for a modified payee/amount → HOLD.
5. **Banking page live:** start session → code appears on the "trusted device" → verify → approve the exact
   change → run → AUTHORIZED; change the amount and re-run → HOLD (approval no longer matches).
6. **Exam page (Chrome):** consent → capture reference → verify 5 live frames → FACE_MATCH_SUPPORTED, liveness
   still listed as unproven; a second person in frame → MULTIPLE_FACES_DETECTED → proctor review, no accusation.
7. **Audit history:** hash chain intact.
