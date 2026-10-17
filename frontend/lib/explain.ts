// Built-in explainer knowledge base (works offline, no API key). Each topic gives a plain-language
// explanation; some topics also read the data on screen to explain *this* result.

export type Topic = { id: string; title: string; keywords: string[]; text: (data?: any) => string[] };

const OUTCOME_TEXT: Record<string, string> = {
  VERIFIED_AND_AUTHORIZED: 'All mandatory checks for this kind of request passed, so the action may go ahead.',
  HOLD_FOR_VERIFICATION: 'Something mandatory is missing, so the action is paused until the person completes an independent check. It is not an accusation.',
  DENIED: 'The request breaks a hard rule (for example asking for an OTP, a replayed code, or a role that is not allowed). It is refused.',
  ESCALATED_FOR_REVIEW: 'The evidence conflicts or looks risky, so a human reviewer decides. The system never makes this call alone.',
};

export const TOPICS: Topic[] = [
  {
    id: 'overview', title: 'What is GHOSTKEY?', keywords: ['ghostkey', 'what is', 'overview', 'how does', 'project', 'about'],
    text: () => [
      'GHOSTKEY checks whether a person is really who they claim to be before a sensitive action happens — sending money, changing a payout account, starting an exam.',
      'It never trusts a voice, face, phone number or account on its own. Several specialist agents look at the evidence, a critic agent challenges them, and a fixed rulebook (the policy engine) makes the final decision.',
      'Voice checks use DetectifAI\'s real API; face checks use an open-source OpenCV model running on our server.',
    ],
  },
  {
    id: 'decision', title: 'The final decision', keywords: ['decision', 'verdict', 'outcome', 'why', 'held', 'hold', 'denied', 'escalated', 'verified', 'result'],
    text: (rec?: any) => {
      if (!rec?.decision) return Object.entries(OUTCOME_TEXT).map(([k, v]) => `**${k.replaceAll('_', ' ')}** — ${v}`);
      const d = rec.decision;
      const unmet = d.requirements.filter((r: any) => !r.satisfied && !r.name.includes('informational'));
      return [
        `**${d.outcome.replaceAll('_', ' ')}** — ${OUTCOME_TEXT[d.outcome]}`,
        unmet.length ? `What was missing or failed: ${unmet.map((r: any) => `**${r.name.replaceAll('_', ' ')}** (${r.detail})`).join('; ')}.` : 'Every listed requirement was met.',
        `In plain words: ${d.reasons.at(-1)}`,
        'This decision comes from the deterministic policy engine — fixed rules, not an AI opinion — so no amount of convincing audio can override it.',
      ];
    },
  },
  {
    id: 'requirements', title: 'Policy requirements', keywords: ['requirement', 'checklist', 'rule', 'policy', 'tick', 'cross'],
    text: (rec?: any) => [
      'Each use case has a policy profile listing what must be true before an action is allowed. A ✅ means that requirement was met; ⛔ means it was not.',
      rec?.decision ? `This case used the **${rec.decision.profile.split(':')[0]}** profile: ${rec.decision.profile.split(':').slice(1).join(':').trim()}` : '',
      'Items marked "informational" (like the voice result in banking) are shown for context but can never authorize anything by themselves.',
    ].filter(Boolean),
  },
  {
    id: 'pipeline', title: 'The investigation pipeline', keywords: ['pipeline', 'flow', 'steps', 'stages', 'process'],
    text: () => [
      '1. **Evidence** — DetectifAI analyses the voice, the face model analyses camera frames, and the session service checks codes and approvals.',
      '2. **Specialist agents** — each agent reads only its own evidence and writes a structured finding.',
      '3. **Adversarial critic** — challenges weak conclusions (e.g. "a voice match does not rule out a clone").',
      '4. **Reconciler** — records who changed their mind and which disagreements are still open.',
      '5. **Policy engine** — applies fixed rules and gives the final outcome.',
    ],
  },
  {
    id: 'agents', title: 'The specialist agents', keywords: ['agent', 'finding', 'specialist', 'voice agent', 'speaker agent'],
    text: () => [
      '**Voice Authenticity** — reads DetectifAI\'s deepfake verdict. It only says whether audio sounds AI-generated, never who is speaking.',
      '**Speaker Identity** — compares the voice with an enrolled voiceprint using DetectifAI speaker verification.',
      '**Exam Identity** — compares webcam frames with the student\'s enrolled reference using a real face model.',
      '**SIM & Lifecycle Risk** — looks at (simulated) carrier events such as a number being reassigned.',
      '**Insurance Claim** — checks the claim record for missing documents, duplicates, payout changes and timing anomalies.',
      '**Contextual Risk** — judges how dangerous the requested action is and what evidence is still missing.',
      'Agents are rule-based Python modules — not chatbots — so their reasoning is predictable and testable.',
    ],
  },
  {
    id: 'critic', title: 'Adversarial critic & debate', keywords: ['critic', 'debate', 'challenge', 'adversarial', 'disagree', 'revised', 'defended'],
    text: (rec?: any) => [
      'The critic\'s job is to argue against the other agents, so mistakes are caught before the decision.',
      'Each challenge ends as **defended** (the agent stood by its finding), **revised** (it changed or narrowed the finding) or **retracted**.',
      rec?.challenges?.length ? `In this case the critic raised ${rec.challenges.length} challenge(s); ${rec.challenges.filter((c: any) => c.outcome === 'revised').length} led to a revision.` : '',
      'Disagreements that survive are shown as "unresolved" and usually send the case to a human reviewer.',
    ].filter(Boolean),
  },
  {
    id: 'timeline', title: 'Investigation timeline', keywords: ['timeline', 'time', 'order', 'log', 'history of case'],
    text: () => [
      'The timeline shows every step of this investigation in order, with the time since the start in seconds.',
      'Colours show the step type: provider evidence, agent findings, critic challenges, agent responses, reconciliation and the final policy decision.',
    ],
  },
  {
    id: 'evidence', title: 'Facts vs predictions vs hypotheses', keywords: ['fact', 'prediction', 'hypothesis', 'evidence summary', 'reconciler', 'reconciliation'],
    text: () => [
      '**Observed facts** — things directly recorded: a provider response, a carrier event, a missing document.',
      '**Model predictions** — outputs of AI models, such as "synthetic indicators" from DetectifAI or a face similarity score.',
      '**Hypotheses** — interpretations, such as "this action is high risk".',
      'Keeping them separate stops a guess from being treated like a fact.',
    ],
  },
  {
    id: 'sources', title: 'Where the evidence came from', keywords: ['source', 'simulated', 'real', 'live', 'badge', 'fixture', 'provider output'],
    text: () => [
      '**Real DetectifAI output** — a live API response from DetectifAI for this exact audio.',
      '**Local face model** — computed by the OpenCV face model on our server.',
      '**Case data** — read from the (synthetic) case record by a rule-based agent.',
      '**SIMULATED** — a labelled demo fixture used by a scenario; it is never presented as a real provider result.',
    ],
  },
  {
    id: 'voice', title: 'Voice deepfake detection', keywords: ['voice', 'deepfake', 'synthetic', 'ai voice', 'fake', 'score', 'detectif', 'aletheia'],
    text: () => [
      'DetectifAI\'s deepfake model (Aletheia) scores audio from 0 to 1; higher means more likely AI-generated. Its own threshold is 0.62 and it returns real, fake or not_sure.',
      'The score is a vendor score, not a calibrated probability, so GHOSTKEY keeps "confidence" empty and uses the verdict as evidence only.',
      'DetectifAI\'s docs warn that phone-quality audio and voice notes are less reliable, and that the check is tuned for English.',
    ],
  },
  {
    id: 'speaker', title: 'Speaker verification', keywords: ['speaker', 'voiceprint', 'enroll', 'match', 'similarity', 'eidos'],
    text: () => [
      'Speaker verification (DetectifAI Eidos) compares a new recording with an enrolled voiceprint and returns match or no_match with a similarity score (−1 to 1).',
      'A match does NOT prove the audio is human — a voice clone of the enrolled person can match. That is why GHOSTKEY always combines it with the deepfake check and independent authentication.',
    ],
  },
  {
    id: 'face', title: 'Face verification states', keywords: ['face', 'exam', 'student', 'camera', 'webcam', 'mismatch', 'liveness', 'proctor'],
    text: () => [
      '**FACE_MATCH_SUPPORTED** — frames resemble the enrolled reference (cosine similarity ≥ 0.363, OpenCV\'s published threshold).',
      '**FACE_MISMATCH_SUSPECTED** — a different-looking person; sent to a proctor, never an automatic cheating verdict.',
      '**MULTIPLE_FACES_DETECTED**, **NO_FACE_DETECTED**, **LIVENESS_INCONCLUSIVE** (too dark or identical frames), **REFERENCE_IMAGE_MISSING**.',
      'Similarity is not liveness: there is no anti-spoofing model, so a match still lists "liveness unproven".',
    ],
  },
  {
    id: 'sim', title: 'SIM swaps & number reassignment', keywords: ['sim', 'number', 'reassign', 'swap', 'carrier', 'phone number', 'family'],
    text: () => [
      'Phone numbers get recycled after inactivity, and criminals can hijack them with SIM-swap fraud. A familiar number therefore proves nothing about who is calling.',
      'GHOSTKEY has no telecom integration: carrier events here are clearly labelled simulations.',
      'For family money requests the rule is simple: verify through an independent, pre-enrolled channel (a code to the relative\'s recovery email, a call-back) before sending anything.',
    ],
  },
  {
    id: 'insurance', title: 'Insurance claim checks', keywords: ['insurance', 'claim', 'payout', 'policy', 'nominee', 'premium', 'duplicate'],
    text: () => [
      'All insurance records are synthetic demo data. The claim agent looks for missing documents, duplicate claim references, recent payout-account changes, claims shortly after a policy starts and late reporting.',
      'These are indicators for a claims officer, not proof of fraud. Payout or contact changes always need a fresh code plus a trusted-device approval bound to that exact change.',
    ],
  },
  {
    id: 'session', title: 'Codes, approvals and replay protection', keywords: ['code', 'challenge', 'otp', 'approval', 'trusted device', 'replay', 'session', 'device'],
    text: () => [
      'A **challenge** is a one-time code shown only on the person\'s enrolled device. It expires in 2 minutes and works once; a reused code is rejected as a replay.',
      'An **approval** is tied to a fingerprint (SHA-256) of the exact action. If anyone changes the amount or account afterwards, the old approval stops working.',
      'The trusted device here is simulated on screen; it is not WebAuthn or passkeys.',
    ],
  },
  {
    id: 'examples', title: 'Real human examples', keywords: ['example', 'dataset', 'minds', 'caltech', 'real human', 'sample'],
    text: () => [
      'Face examples are real photos from the Caltech Faces 1999 research dataset (MIT licence), grouped by person with the face model. Darkening, side-by-side and repeated frames are labelled transformations.',
      'Voice examples are real people calling a bank helpline from MINDS-14 (CC BY 4.0). The family or insurance story around each call is synthetic. A few AI-voice examples (Microsoft neural TTS) are added for contrast.',
      '"Run" is free and skips the voice check (shown as missing evidence). "Analyse with DetectifAI" spends 1 check and uses the live result.',
    ],
  },
  {
    id: 'status', title: 'Integration status', keywords: ['status', 'credits', 'connected', 'health', 'integration', 'settings'],
    text: () => [
      'Shows whether DetectifAI is reachable, whether the API key is configured on the backend (the key itself is never sent to the browser), and how many credits remain. Each check costs 50 credits on the free plan.',
      'It also shows the face model and that orchestration runs inside FastAPI.',
    ],
  },
];

export function topicById(id: string) {
  return TOPICS.find((t) => t.id === id);
}

export function answer(question: string, data?: any): { title: string; lines: string[] } {
  const q = question.toLowerCase();
  let best: Topic | undefined;
  let score = 0;
  for (const t of TOPICS) {
    const s = t.keywords.reduce((n, k) => n + (q.includes(k) ? k.length : 0), 0) + (q.includes(t.title.toLowerCase()) ? 20 : 0);
    if (s > score) {
      score = s;
      best = t;
    }
  }
  if (!best) return { title: 'I can explain these topics', lines: TOPICS.map((t) => `• ${t.title}`) };
  return { title: best.title, lines: best.text(data) };
}
