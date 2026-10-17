# GHOSTKEY 2.0: speaker verification fix, test reporting, light UI redesign

Date: 2026-10-17. Every result below comes from tests that actually ran.

## 1. Speaker verification: root-cause analysis

**Symptom:** a person enrolled their voice, then tested with a different person's voice and got the same result.

**What I inspected:** the audit log, the stored investigations, DetectifAI's `/v1/speakers` and `/v1/usage` records, and the full code path:

1. Recording and upload.
2. Enrollment endpoint and the speaker ID stored for each person.
3. The verify request, including which speaker ID and which audio are sent.
4. Parsing of DetectifAI's response.
5. Agents and the policy engine.
6. Frontend state.

### Confirmed root cause

**The final decision ignored the speaker check.** `policy_engine.py` only consulted the speaker result for insurance payout-account changes. Everywhere else, the outcome came only from the example scenario's built-in context:
- **Banking:** non-sensitive requests were approved outright.
- **Family:** requests were approved once independent verification was marked as passed.

Evidence from the stored judge tests:

| Judge test | Speaker check | Final decision | Reason |
|---|---|---|---|
| `inv_b87a2b66e700` (Family F01) | **failed** (1.2 s of speech) | **VERIFIED_AND_AUTHORIZED** | "Identity confirmed independently over the enrolled recovery channel" |
| `inv_dc3a4ac4fe3b` (Banking B01) | match 0.77 | VERIFIED_AND_AUTHORIZED | "Non-sensitive request" |

In both cases the decision would have been the same for any voice.

The DetectifAI integration itself was correct:
- Each voiceprint holds one sample.
- Earlier verifications of the same voiceprint returned both `match` and `no_match`.
- The live test below separates two real speakers.

### Contributing problems (also fixed)

1. **Re-enrolling blended voiceprints.** DetectifAI's enroll endpoint *adds* a sample to an existing speaker ID (up to 5). Re-enrolling a person with a different voice therefore mixed two people into one voiceprint, and both would match. Re-enrollment now deletes the old voiceprint first.
2. **Silent or very quiet recordings were accepted.** Your verify attempt had 0.4 s of detectable speech. Enrollment now refuses a sample with less than 3 s of speech before it reaches DetectifAI. The recorder shows a live level meter and a microphone picker.
3. **Stale results.** The page could show a previous result next to a new recording.
   - Every attempt now has a unique `attempt_id`, and responses for older attempts are dropped.
   - The result is cleared whenever the person, the file or the expectation changes.
   - The report stores the SHA-256 of the submitted audio and the `speaker_id` that was sent.

### The fix

**New rule R13** in `policy_engine.py`. It applies when a voiceprint check was actually attempted:

| Speaker check result | Effect on the decision |
|---|---|
| `no_match` | Never VERIFIED. **DENIED** if nothing else held the request; otherwise kept as HOLD or ESCALATED (for example scenario G, where the code and device approval passed), with the headline "Speaker mismatch detected". |
| Failed or inconclusive | **HOLD_FOR_VERIFICATION** ("Speaker could not be confirmed — retry needed") |
| Not attempted | No change: the profile rules decide (scenario K is unchanged) |

Every decision now also carries a generated `headline` for the result screen.

## 2. Test reporting

- **`app/report_service.py`** combines the report service, repository, serializer, export, interrupted-run recovery and status helpers in one module.
- **Table:** `test_reports` in SQLite.
- **Lifecycle:** each report is created as RUNNING, saved after every step, and finished as PASS, FAIL, HOLD, ERROR or SKIPPED.
- **Interrupted runs:** on startup, reports still RUNNING from an earlier process are marked `ERROR / incomplete`.
- **Coverage:**
  - deepfake check
  - enrollment
  - speaker verification
  - every multi-agent investigation (scenarios, examples, judge tests, live family / banking / insurance / exam)
  - connectivity check
  - backend test suite (`POST /api/reports/selftest`)
  - frontend integration smoke test (sent through `POST /api/reports/ingest`)
- **Status rules:**
  - Execution status (did it run?) is stored separately from test status (were the acceptance criteria met?).
  - If you declare an expectation, the test passes or fails against it. Options: same person / different person / AI voice / real human, or a scenario's expected outcome.
  - Otherwise: verified = PASS, rejected = FAIL, held or inconclusive = HOLD, infrastructure problem = ERROR.
  - HTTP 200 alone never gives PASS.
- **Sanitising:** secrets (API key, internal token, Bearer values) are removed, and biometric vectors and audio bytes are left out. Audio is identified by its SHA-256 only.
- **API:** `GET /api/reports` (search, status, feature, provider, date filters, sorting), `/api/reports/stats`, `/api/reports/{id}`, `/api/reports/{id}/export` (downloads JSON).
- **UI:**
  - `/reports`: counts, filters, sortable history, and buttons to run the three free tests.
  - `/reports/{id}`: final assessment, expected vs actual, acceptance criteria, inputs, live execution timeline, evidence, diagnostics (hypotheses kept separate from confirmed causes), JSON download and a print view.

## 3. UI redesign (light theme)

- **Design tokens:** off-white surfaces, cool-grey background, graphite text, electric blue accent; teal = verified, amber = pending, red = failed.
- **Status display:** always icon + text, never colour alone.
- **Animation:** Motion 12 (MIT), with `MotionConfig reducedMotion="user"` plus a CSS reduced-motion fallback.
- **Result screen** (`components/viz.tsx`, used in every module):
  1. Overall result card with an animated check, warning or cross. Its label says whether it is a policy decision, a speaker outcome or a deepfake result.
  2. Voice-authenticity meter. The score and threshold marker are drawn only when DetectifAI returns them.
  3. Enrolled speaker ↔ submitted voice, with match / rejected / inconclusive / could not verify, and the similarity bar with its documented threshold.
  4. Agent pipeline showing disagreements and critic revisions.
  5. Categorical action-risk scale, labelled as local rules.
  6. Five expandable evidence cards.
  7. A one-line decision reason with expandable supporting evidence.
  8. **View test report** button.
- **Speaker verification page:** guided 4-step flow. The progress display is labelled as application-side, not model progress.
- **Dashboard:** provider status, alerts, test outcomes taken from stored reports, quick actions, recent reports, and a workflow diagram.
- **Reusable pieces:** loading skeletons, error banners (linking to the report), and empty states.

## 4. Test results (actually run)

| Suite | Command | Result |
|---|---|---|
| Backend unit + regression (mocked provider, labelled MOCK) | `.venv/Scripts/python -m pytest -q` | **90 passed, 1 skipped** (the skipped one is the live test, opt-in) |
| Same suite through the app | Reports → Backend test suite | PASS, 90/91 (1 skipped), stored as a report |
| **Real DetectifAI integration** | `GHOSTKEY_LIVE_TESTS=1 .venv/Scripts/python -m pytest -q tests/test_detectifai_live.py -s` | **1 passed**: real caller A enrolled; A's other audio → **match 0.838**; different real caller B → **no_match 0.237** (threshold 0.53). Both reports persisted. About 300 credits. |
| Real end-to-end in the UI | Speaker verification, expectation "Different person" | WhatsApp voice note vs Zira's voiceprint → **NOT VERIFIED, similarity 0.119**, test PASS |
| Frontend integration smoke test | Reports → Frontend integration | PASS, 9/9 checks |
| Connectivity | Reports → API connectivity | PASS |
| Typecheck / production build | `npx tsc --noEmit`, `NEXT_DIST_DIR=.next-build npx next build` | clean / build OK (15 routes) |

The speaker matrix in `tests/test_reports_and_speakers.py` covers all 12 requested cases with the mocked provider, plus:
- re-enrollment replacing the voiceprint;
- failed enrollment not being stored;
- regression tests for the root cause;
- the report-system tests: persistence, HOLD and ERROR reports, restart survival, case linking, export equality, secret redaction, missing optional fields, and interrupted runs.

## 5. Commands

```bash
# run the app (from ghostkey/frontend)
npm run dev:all
# backend tests (from ghostkey/backend)
.venv/Scripts/python -m pytest -q
# real DetectifAI integration test (spends credits)
GHOSTKEY_LIVE_TESTS=1 .venv/Scripts/python -m pytest -q tests/test_detectifai_live.py -s
# production build without disturbing a running dev server (from ghostkey/frontend)
NEXT_DIST_DIR=.next-build npx next build
```

## 6. Limitations and open items

- **Short samples:** DetectifAI requires 15–60 s for enrollment, so shorter samples are repeated up to 16 s. This is stated in the result and the report. A 15 s+ natural sample gives a stronger voiceprint.
- **Mocks vs live:** the speaker matrix in unit tests uses a labelled mock. Only the live test and the UI run above prove DetectifAI's real behaviour, and the live test covered two speakers, not a large population.
- **Frontend tests:** there is no component-test framework. Frontend integration is covered by the in-browser smoke test, which stores a report.
- **Stored data:** reports are kept in SQLite with no retention purge, unlike case records.
- **Git:** no repository exists, so the report's `git_commit` is empty unless `GHOSTKEY_GIT_COMMIT` is set.
- **Downloads picker:** it exposes the host's Downloads audio. Set `GHOSTKEY_LOCAL_DOWNLOADS=0` before any public link.
- **Face verification:** liveness is still not proven (no presentation-attack model).
