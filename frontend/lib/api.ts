export class ApiError extends Error {
  status: number;
  reportId?: string;
  code?: string;
  constructor(message: string, status: number, reportId?: string, code?: string) {
    super(message);
    this.status = status;
    this.reportId = reportId;
    this.code = code;
  }
}

export async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/${path}`, { cache: 'no-store', ...init });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = body.detail;
    const msg = typeof d === 'string' ? d : d?.message ?? JSON.stringify(d ?? body);
    throw new ApiError(msg, res.status, body.report_id ?? d?.report_id, body.code ?? d?.code);
  }
  return body as T;
}

export const postJson = <T = any>(path: string, data: unknown) =>
  api<T>(path, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(data) });

export const postForm = <T = any>(path: string, form: FormData) => api<T>(path, { method: 'POST', body: form });

export const OUTCOME_STYLE: Record<string, string> = {
  VERIFIED_AND_AUTHORIZED: 'st-pass',
  HOLD_FOR_VERIFICATION: 'st-hold',
  DENIED: 'st-fail',
  ESCALATED_FOR_REVIEW: 'st-hold',
};

/** Final security-policy decision → the four result-screen states. */
export const RESULT: Record<string, { label: string; tone: 'pass' | 'fail' | 'hold' | 'error'; color: string; soft: string }> = {
  VERIFIED_AND_AUTHORIZED: { label: 'VERIFIED', tone: 'pass', color: 'var(--good)', soft: 'var(--good-soft)' },
  DENIED: { label: 'NOT VERIFIED', tone: 'fail', color: 'var(--bad)', soft: 'var(--bad-soft)' },
  HOLD_FOR_VERIFICATION: { label: 'HOLD FOR REVIEW', tone: 'hold', color: 'var(--warn)', soft: 'var(--warn-soft)' },
  ESCALATED_FOR_REVIEW: { label: 'HOLD FOR REVIEW', tone: 'hold', color: 'var(--warn)', soft: 'var(--warn-soft)' },
  ERROR: { label: 'TECHNICAL ERROR', tone: 'error', color: '#9f1239', soft: '#fff1f2' },
};

/** Test-report statuses (test acceptance, not HTTP success). */
export const STATUS: Record<string, { label: string; cls: string; color: string }> = {
  PASS: { label: 'Pass', cls: 'st-pass', color: 'var(--good)' },
  FAIL: { label: 'Fail', cls: 'st-fail', color: 'var(--bad)' },
  HOLD: { label: 'Hold', cls: 'st-hold', color: 'var(--warn)' },
  ERROR: { label: 'Error', cls: 'st-error', color: '#9f1239' },
  SKIPPED: { label: 'Skipped', cls: 'st-skip', color: 'var(--ink3)' },
  RUNNING: { label: 'Running', cls: 'st-run', color: 'var(--accent)' },
};

export const CATEGORY_LABEL: Record<string, string> = {
  voice_deepfake: 'Voice deepfake', speaker_enrollment: 'Speaker enrollment', speaker_verification: 'Speaker verification',
  face_verification: 'Face verification', family_sim_risk: 'Family & SIM', insurance_claim: 'Insurance claim', banking_voice: 'Banking',
  connectivity: 'Connectivity', automated_backend_tests: 'Backend test suite', frontend_integration: 'Frontend integration',
};

export const fmtTime = (iso?: string | null) => (iso ? new Date(iso).toLocaleString() : '—');
