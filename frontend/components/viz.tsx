'use client';
/**
 * Reusable visual result components. Every value shown comes from the backend response; nothing is invented:
 * no score is drawn unless the provider returned one, and animations only replay states that already exist.
 */
import Link from 'next/link';
import { useState } from 'react';
import { motion } from 'motion/react';
import {
  AlertOctagon, AlertTriangle, ArrowRight, Bot, CheckCircle2, ChevronDown, CircleDashed, CircleHelp, ClipboardCheck, Cpu, FileWarning,
  Fingerprint, GitBranch, Hourglass, Mic, Radio, Scale, ScanFace, ShieldCheck, Smartphone, Split, Swords, Umbrella, UserRound, XCircle,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { RESULT, STATUS } from '@/lib/api';

const ease = [0.22, 1, 0.36, 1] as const;

/* ---------------- status pill (icon + text, never colour alone) ---------------- */
const STATUS_ICON: Record<string, LucideIcon> = { PASS: CheckCircle2, FAIL: XCircle, HOLD: Hourglass, ERROR: AlertOctagon, SKIPPED: CircleDashed, RUNNING: CircleDashed };
export function StatusPill({ status, size = 'sm' }: { status: string; size?: 'sm' | 'md' }) {
  const s = STATUS[status] ?? STATUS.SKIPPED;
  const Icon = STATUS_ICON[status] ?? CircleHelp;
  return (
    <span className={`chip ${s.cls} ${size === 'md' ? '!px-3 !py-1 !text-[13px]' : ''}`}>
      <Icon size={size === 'md' ? 14 : 12} className={status === 'RUNNING' ? 'animate-spin' : ''} /> {s.label}
    </span>
  );
}

export function ReportButton({ id, className = '' }: { id?: string; className?: string }) {
  if (!id) return null;
  return (
    <Link href={`/reports/${id}`} className={`btn group ${className}`}>
      <ClipboardCheck size={15} className="text-[var(--accent)]" /> View test report
      <ArrowRight size={14} className="transition-transform group-hover:translate-x-0.5" />
    </Link>
  );
}

export function ErrorBanner({ error, reportId, onRetry }: { error: string; reportId?: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-wrap items-center gap-3 rounded-none border border-[#f6c5c5] bg-[var(--bad-soft)] px-3.5 py-2.5 text-sm text-[#991b1b]">
      <AlertTriangle size={16} className="shrink-0" />
      <span className="min-w-0 flex-1">{error}</span>
      {onRetry && <button className="btn !py-1 text-[13px]" onClick={onRetry}>Retry</button>}
      {reportId && <ReportButton id={reportId} className="!py-1 text-[13px]" />}
    </div>
  );
}

export const Skeleton = ({ className = '' }: { className?: string }) => <div className={`skeleton ${className}`} aria-hidden="true" />;

/* ---------------- animated result glyph ---------------- */
function Glyph({ tone }: { tone: 'pass' | 'fail' | 'hold' | 'error' }) {
  const color = { pass: 'var(--good)', fail: 'var(--bad)', hold: 'var(--warn)', error: '#9f1239' }[tone];
  const path = { pass: 'M14 25 l7 7 l13 -15', fail: 'M16 16 l16 16 M32 16 l-16 16', hold: 'M24 14 v13 M24 33 v0.5', error: 'M24 14 v13 M24 33 v0.5' }[tone];
  return (
    <svg viewBox="0 0 48 48" className="h-14 w-14" aria-hidden="true">
      <motion.circle cx="24" cy="24" r="21" fill="none" stroke={color} strokeWidth="3" strokeOpacity="0.25" />
      <motion.circle cx="24" cy="24" r="21" fill="none" stroke={color} strokeWidth="3" strokeLinecap="round" transform="rotate(-90 24 24)"
        initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.5, ease }} />
      <motion.path d={path} fill="none" stroke={color} strokeWidth="3.6" strokeLinecap="round" strokeLinejoin="round"
        initial={{ pathLength: 0, opacity: 0 }} animate={{ pathLength: 1, opacity: 1 }} transition={{ delay: 0.35, duration: 0.35, ease }} />
    </svg>
  );
}

/** Large overall result card. `kind` says WHAT this result is (policy decision vs speaker check vs deepfake check). */
export function ResultHero({ outcome, headline, kind, title, at, reportId, children }: {
  outcome: string; headline?: string; kind: string; title?: string; at?: number | string; reportId?: string; children?: React.ReactNode;
}) {
  const r = RESULT[outcome] ?? RESULT.ERROR;
  const when = at ? new Date(typeof at === 'number' ? at * 1000 : at) : null;
  return (
    <motion.section initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, ease }}
      className="relative overflow-hidden rounded-none border bg-[var(--panel)] p-5 shadow-[var(--shadow)] md:p-6" style={{ borderColor: `color-mix(in srgb, ${r.color} 30%, var(--line))` }}>
      <div className="pointer-events-none absolute inset-x-0 top-0 h-1" style={{ background: r.color }} />
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="grid place-items-center rounded-none p-1" style={{ background: r.soft }}><Glyph tone={r.tone} /></div>
          <div>
            <div className="eyebrow">{kind}</div>
            <div className="text-[26px] font-extrabold leading-tight tracking-tight md:text-3xl" style={{ color: r.color }}>{r.label}</div>
            {headline && <div className="mt-0.5 text-[15px] font-semibold text-[var(--ink)]">{headline}</div>}
            <div className="mt-0.5 text-xs text-[var(--ink3)]">{title}{title && when ? ' · ' : ''}{when ? when.toLocaleString() : ''}</div>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">{children}<ReportButton id={reportId} /></div>
      </div>
    </motion.section>
  );
}

/* ---------------- meter with threshold marker ---------------- */
function ThresholdBar({ value, threshold, lowLabel, highLabel, highIsBad }: { value: number; threshold: number; lowLabel: string; highLabel: string; highIsBad: boolean }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  const thr = Math.max(0, Math.min(1, threshold)) * 100;
  const over = value >= threshold;
  const color = over === highIsBad ? 'var(--bad)' : 'var(--good)';
  return (
    <div>
      <div className="relative h-3 overflow-hidden rounded-full bg-[var(--panel2)]">
        <div className="absolute inset-y-0 left-0" style={{ width: `${thr}%`, background: highIsBad ? 'rgba(13,148,136,.10)' : 'rgba(220,38,38,.08)' }} />
        <div className="absolute inset-y-0 right-0" style={{ width: `${100 - thr}%`, background: highIsBad ? 'rgba(220,38,38,.08)' : 'rgba(13,148,136,.10)' }} />
        <motion.div className="absolute inset-y-0 left-0 rounded-full" style={{ background: color }} initial={{ width: 0 }} animate={{ width: `${pct}%` }} transition={{ duration: 0.7, ease }} />
      </div>
      <div className="relative h-5 text-[10.5px] text-[var(--ink3)]">
        <span className="absolute left-0 top-1">{lowLabel}</span>
        <span className="absolute top-0 -translate-x-1/2 border-l-2 border-[var(--ink)] pl-1 pt-0.5 font-semibold text-[var(--ink2)]" style={{ left: `${thr}%` }}>threshold {threshold}</span>
        <span className="absolute right-0 top-1">{highLabel}</span>
      </div>
    </div>
  );
}

const VOICE_STATE: Record<string, { label: string; color: string; icon: LucideIcon }> = {
  real: { label: 'No synthetic indicators', color: 'var(--good)', icon: CheckCircle2 },
  fake: { label: 'Synthetic (AI) indicators', color: 'var(--bad)', icon: Bot },
  not_sure: { label: 'Inconclusive', color: 'var(--warn)', icon: CircleHelp },
};

/** Provider deepfake assessment. Draws a score only when DetectifAI returned score + threshold. */
export function VoiceMeter({ p }: { p: any | null }) {
  const st = p?.classification ? VOICE_STATE[p.classification] : null;
  const ran = p && ['COMPLETED', 'INCONCLUSIVE'].includes(p.status);
  return (
    <Card icon={Radio} title="Voice authenticity" sub={p?.simulated ? 'SIMULATED fixture' : ran ? 'DetectifAI · deepfake detection' : 'DetectifAI'}>
      {!p ? <Muted icon={CircleDashed} text="Not checked in this test" /> : !ran ? (
        <Muted icon={AlertTriangle} text={p.error?.startsWith('not run') ? 'Not run (free example run)' : `Could not analyse: ${p.error ?? p.status}`} tone="warn" />
      ) : (
        <>
          <div className="mb-3 flex items-center gap-2 text-[15px] font-semibold" style={{ color: st?.color }}>
            {st && <st.icon size={18} />} {st?.label ?? p.classification}
          </div>
          {typeof p.score === 'number' && typeof p.threshold === 'number' ? (
            <ThresholdBar value={p.score} threshold={p.threshold} lowLabel="human-like" highLabel="AI-like" highIsBad />
          ) : <div className="text-xs text-[var(--ink3)]">Provider returned a label only — no score shown.</div>}
          <div className="mt-1 text-[11px] text-[var(--ink3)]">score {p.score ?? '—'} · vendor score, not a probability{p.raw_result_reference ? ` · ${p.raw_result_reference}` : ''}</div>
        </>
      )}
    </Card>
  );
}

const SPEAKER_STATE: Record<string, { label: string; color: string; icon: LucideIcon }> = {
  MATCH: { label: 'Match confirmed', color: 'var(--good)', icon: CheckCircle2 },
  NO_MATCH: { label: 'Match rejected', color: 'var(--bad)', icon: XCircle },
  INCONCLUSIVE: { label: 'Inconclusive', color: 'var(--warn)', icon: CircleHelp },
  NOT_VERIFIED: { label: 'Could not verify', color: 'var(--warn)', icon: AlertTriangle },
  NOT_CHECKED: { label: 'Not checked', color: 'var(--ink3)', icon: CircleDashed },
  CLONE: { label: 'Match, but possible clone', color: 'var(--warn)', icon: AlertTriangle },
};

export function speakerOutcome(p: any | null, findingStatus?: string): keyof typeof SPEAKER_STATE {
  if (findingStatus === 'SPEAKER_MATCH_NOT_SUFFICIENT') return 'CLONE';
  if (findingStatus === 'INCONCLUSIVE') return 'INCONCLUSIVE';
  if (!p) return 'NOT_CHECKED';
  if (p.status !== 'COMPLETED') return 'NOT_VERIFIED';
  return p.classification === 'match' ? 'MATCH' : 'NO_MATCH';
}

/** Enrolled speaker ↔ submitted voice. The comparison is DetectifAI's decision — the waveform proves nothing. */
export function SpeakerCompare({ claimed, speakerId, p, findingStatus, submittedLabel = 'Submitted voice' }: {
  claimed?: string; speakerId?: string; p: any | null; findingStatus?: string; submittedLabel?: string;
}) {
  const o = SPEAKER_STATE[speakerOutcome(p, findingStatus)];
  return (
    <Card icon={Fingerprint} title="Speaker identity" sub={p?.simulated ? 'SIMULATED fixture' : 'DetectifAI · speaker verification'}>
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2">
        <Who icon={UserRound} label="Enrolled speaker" name={claimed ?? '—'} sub={speakerId ? `id ${speakerId}` : p?.simulated ? 'fixture voiceprint' : p ? 'voiceprint on file' : 'no voiceprint'} />
        <div className="flex flex-col items-center gap-1 px-1">
          <motion.div initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ duration: 0.4, ease }} className="h-0.5 w-10 origin-left rounded-none md:w-16" style={{ background: o.color }} />
          <motion.div initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ delay: 0.3, duration: 0.25 }}
            className="grid size-9 place-items-center rounded-full border-2 bg-[var(--panel)]" style={{ borderColor: o.color, color: o.color }}>
            <o.icon size={18} />
          </motion.div>
        </div>
        <Who icon={Mic} label={submittedLabel} name="this recording" sub={p?.details?.duration_seconds ? `${p.details.duration_seconds} s analysed` : ''} />
      </div>
      <div className="mt-3 text-center text-[15px] font-semibold" style={{ color: o.color }}>{o.label}</div>
      {p?.status === 'COMPLETED' && typeof p.score === 'number' && typeof p.threshold === 'number' && (
        <div className="mt-2"><ThresholdBar value={p.score} threshold={p.threshold} lowLabel="different" highLabel="same speaker" highIsBad={false} /></div>
      )}
      {p && p.status !== 'COMPLETED' && p.error && <div className="mt-1 text-center text-xs text-[var(--ink2)]">{p.error}</div>}
      {p?.status === 'COMPLETED' && <div className="mt-1 text-center text-[11px] text-[var(--ink3)]">similarity {p.score} · {p.score_semantics ?? 'not a percentage'}</div>}
    </Card>
  );
}

function Who({ icon: Icon, label, name, sub }: { icon: LucideIcon; label: string; name: string; sub?: string }) {
  return (
    <div className="soft flex min-w-0 flex-col items-center gap-1 p-3 text-center">
      <div className="grid size-10 place-items-center rounded-full bg-[var(--accent-soft)] text-[var(--accent)]"><Icon size={19} /></div>
      <div className="eyebrow !text-[10px]">{label}</div>
      <div className="w-full truncate text-sm font-semibold" title={name}>{name}</div>
      {sub && <div className="mono w-full truncate !text-[10.5px] text-[var(--ink3)]" title={sub}>{sub}</div>}
    </div>
  );
}

/* ---------------- multi-agent pipeline ---------------- */
const AGENT_META: Record<string, { short: string; icon: LucideIcon }> = {
  voice_authenticity_agent: { short: 'Voice', icon: Radio },
  speaker_identity_agent: { short: 'Speaker', icon: Fingerprint },
  exam_identity_agent: { short: 'Face', icon: ScanFace },
  sim_risk_agent: { short: 'SIM', icon: Smartphone },
  insurance_claim_agent: { short: 'Claim', icon: Umbrella },
  contextual_risk_agent: { short: 'Context', icon: Scale },
};
const GOOD = new Set(['NO_SYNTHETIC_INDICATORS', 'SPEAKER_MATCH_SUPPORTED', 'FACE_MATCH_SUPPORTED', 'NO_LIFECYCLE_ANOMALY', 'CLAIM_CONSISTENT', 'LOW_RISK_ACTION']);
const BAD = new Set(['SYNTHETIC_INDICATORS', 'SPEAKER_MISMATCH_SUSPECTED', 'FACE_MISMATCH_SUSPECTED', 'MULTIPLE_FACES_DETECTED', 'NUMBER_REASSIGNMENT_SUSPECTED',
  'ACCOUNT_TAKEOVER_SUSPECTED', 'CLAIM_ANOMALIES_FOUND', 'HIGH_RISK_ACTION']);
export const toneOf = (s?: string) => (!s ? 'var(--ink3)' : GOOD.has(s) ? 'var(--good)' : BAD.has(s) ? 'var(--bad)' : ['UNAVAILABLE', 'NO_REFERENCE'].includes(s) ? 'var(--ink3)' : 'var(--warn)');
export const pretty = (s?: string) => (s ?? '').replaceAll('_', ' ').toLowerCase();

export function AgentPipeline({ rec }: { rec: any }) {
  const disputed = new Set<string>((rec.challenges ?? []).filter((c: any) => c.outcome === 'unresolved').map((c: any) => c.target_agent));
  const nodes = [
    ...rec.findings.map((f: any) => ({
      key: f.agent, ...(AGENT_META[f.agent] ?? { short: f.agent, icon: Bot }), status: f.status, line: (f.observations ?? [])[0] ?? '',
      color: toneOf(f.status), flag: f.disposition === 'revised' ? 'revised by critic' : disputed.has(f.agent) ? 'disputed' : f.execution_status !== 'completed' ? f.execution_status : '',
    })),
    { key: 'critic', short: 'Critic', icon: Swords, status: `${rec.challenges.length} challenge(s)`, line: rec.challenges[0]?.question ?? 'No challenges needed', color: 'var(--accent)', flag: '' },
    { key: 'evidence', short: 'Evidence', icon: GitBranch, status: `${rec.reconciliation.disagreements.length} unresolved`, line: `${rec.reconciliation.claims.length} claims reconciled`,
      color: rec.reconciliation.disagreements.length ? 'var(--warn)' : 'var(--good)', flag: '' },
    { key: 'policy', short: 'Policy', icon: ShieldCheck, status: RESULT[rec.decision.outcome]?.label ?? rec.decision.outcome, line: rec.decision.headline || rec.decision.reasons.at(-1),
      color: RESULT[rec.decision.outcome]?.color ?? 'var(--ink2)', flag: '' },
  ];
  return (
    <Card icon={Cpu} title="Multi-agent activity" sub="specialists → critic → reconciler → deterministic policy">
      <div className="flex gap-2 overflow-x-auto pb-1">
        {nodes.map((n, i) => (
          <div key={n.key} className="flex items-stretch gap-2">
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.09, duration: 0.25, ease }}
              className="flex w-[150px] shrink-0 flex-col gap-1 rounded-none border bg-[var(--panel)] p-2.5" style={{ borderColor: `color-mix(in srgb, ${n.color} 35%, var(--line))` }}>
              <div className="flex items-center gap-1.5">
                <motion.span initial={{ scale: 0.5 }} animate={{ scale: 1 }} transition={{ delay: i * 0.09 + 0.1, type: 'spring', stiffness: 400, damping: 18 }}
                  className="grid size-7 place-items-center rounded-none" style={{ background: `color-mix(in srgb, ${n.color} 14%, var(--panel))`, color: n.color }}>
                  <n.icon size={15} />
                </motion.span>
                <span className="text-[13px] font-semibold">{n.short}</span>
              </div>
              <div className="text-[11.5px] font-semibold capitalize" style={{ color: n.color }}>{pretty(n.status)}</div>
              <div className="line-clamp-2 text-[11px] leading-snug text-[var(--ink2)]" title={n.line}>{n.line}</div>
              {n.flag && <span className="mt-auto inline-flex w-fit items-center gap-1 rounded-none bg-[var(--warn-soft)] px-1.5 text-[10px] font-semibold text-[var(--warn)]"><Split size={10} /> {n.flag}</span>}
            </motion.div>
            {i < nodes.length - 1 && <div className="flex items-center"><ArrowRight size={14} className="text-[var(--ink3)]" /></div>}
          </div>
        ))}
      </div>
    </Card>
  );
}

/* ---------------- categorical risk scale (local rules, not a provider score) ---------------- */
export function RiskScale({ status }: { status?: string }) {
  const level = status === 'HIGH_RISK_ACTION' ? 2 : status === 'MODERATE_RISK_ACTION' ? 1 : status === 'LOW_RISK_ACTION' ? 0 : -1;
  const segs = [['Low', 'var(--good)'], ['Moderate', 'var(--warn)'], ['High', 'var(--bad)']];
  return (
    <Card icon={Scale} title="Action risk" sub="local rule-based category · not a provider score">
      {level < 0 ? <Muted icon={CircleDashed} text="No action-risk finding" /> : (
        <>
          <div className="flex gap-1.5">
            {segs.map(([l, c], i) => (
              <motion.div key={l} initial={{ opacity: 0.3 }} animate={{ opacity: i <= level ? 1 : 0.25 }} transition={{ delay: i * 0.12 }}
                className="h-3 flex-1 rounded-full" style={{ background: c }} />
            ))}
          </div>
          <div className="mt-2 flex justify-between text-[11px] text-[var(--ink3)]">{segs.map(([l]) => <span key={l}>{l}</span>)}</div>
          <div className="mt-1 text-[15px] font-semibold" style={{ color: segs[level][1] }}>{segs[level][0]} risk</div>
        </>
      )}
    </Card>
  );
}

/* ---------------- evidence cards ---------------- */
export function EvidenceCards({ rec }: { rec: any }) {
  const f = (t: string) => rec.findings.find((x: any) => x.finding_type === t);
  const identity = f('speaker_identity') ?? f('exam_identity');
  const voice = f('voice_authenticity');
  const ctx = rec.findings.filter((x: any) => ['number_lifecycle', 'claim_consistency', 'action_risk'].includes(x.finding_type));
  const missing = rec.decision.requirements.filter((r: any) => !r.satisfied && !r.name.includes('informational') && r.name !== 'role_permission');
  const conflicts = [...rec.reconciliation.disagreements, ...rec.findings.flatMap((x: any) => x.contradictions ?? [])];
  const cards = [
    { icon: Fingerprint, title: 'Identity evidence', value: identity ? pretty(identity.status) : 'none', color: toneOf(identity?.status), items: identity?.observations ?? [] },
    { icon: Radio, title: 'Voice evidence', value: voice ? pretty(voice.status) : 'not applicable', color: toneOf(voice?.status), items: voice?.observations ?? [] },
    { icon: Scale, title: 'Contextual signals', value: `${ctx.length} signal(s)`, color: ctx.some((x: any) => BAD.has(x.status)) ? 'var(--bad)' : 'var(--ink2)',
      items: ctx.map((x: any) => `${pretty(x.finding_type)}: ${pretty(x.status)}`) },
    { icon: FileWarning, title: 'Missing evidence', value: missing.length ? `${missing.length} missing` : 'none', color: missing.length ? 'var(--warn)' : 'var(--good)',
      items: missing.map((r: any) => `${pretty(r.name)} — ${r.detail}`) },
    { icon: Split, title: 'Conflicting evidence', value: conflicts.length ? `${conflicts.length} conflict(s)` : 'none', color: conflicts.length ? 'var(--warn)' : 'var(--good)', items: conflicts },
  ];
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {cards.map((c, i) => <EvidenceCard key={c.title} {...c} delay={i * 0.05} />)}
    </div>
  );
}

function EvidenceCard({ icon: Icon, title, value, color, items, delay }: { icon: LucideIcon; title: string; value: string; color: string; items: string[]; delay: number }) {
  const [open, setOpen] = useState(false);
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay, duration: 0.25 }} className="panel panel-hover !p-3.5">
      <button className="flex w-full items-start gap-2.5 text-left" onClick={() => setOpen((o) => !o)} aria-expanded={open} disabled={!items.length}>
        <span className="grid size-8 shrink-0 place-items-center rounded-none" style={{ background: `color-mix(in srgb, ${color} 13%, var(--panel))`, color }}><Icon size={16} /></span>
        <span className="min-w-0 flex-1">
          <span className="block text-[12px] text-[var(--ink2)]">{title}</span>
          <span className="block truncate text-[14px] font-semibold capitalize" style={{ color }}>{value}</span>
        </span>
        {items.length > 0 && <ChevronDown size={15} className={`mt-1 text-[var(--ink3)] transition-transform ${open ? 'rotate-180' : ''}`} />}
      </button>
      {open && (
        <motion.ul initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} className="mt-2 space-y-1 border-t border-[var(--line)] pt-2 text-[12px] text-[var(--ink2)]">
          {items.slice(0, 8).map((t, i) => <li key={i}>• {t}</li>)}
        </motion.ul>
      )}
    </motion.div>
  );
}

/* ---------------- execution timeline (progressive) ---------------- */
const STEP_ICON: Record<string, [LucideIcon, string]> = {
  completed: [CheckCircle2, 'var(--good)'], failed: [XCircle, 'var(--bad)'], skipped: [CircleDashed, 'var(--ink3)'], running: [Hourglass, 'var(--accent)'],
};
export function Timeline({ steps }: { steps: { name: string; status: string; detail?: string; at_utc?: string | null; duration_ms?: number | null }[] }) {
  return (
    <ol className="relative ml-3 border-l-2 border-[var(--line)]">
      {steps.map((s, i) => {
        const [Icon, color] = STEP_ICON[s.status] ?? STEP_ICON.completed;
        return (
          <motion.li key={i} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: Math.min(i, 20) * 0.04, duration: 0.2 }} className="relative pb-3 pl-6">
            <span className="absolute -left-[11px] top-0.5 grid size-5 place-items-center rounded-full bg-[var(--panel)]" style={{ color }}><Icon size={18} /></span>
            <div className="flex flex-wrap items-baseline gap-x-2 text-sm">
              <span className="font-semibold">{s.name}</span>
              {s.duration_ms != null && <span className="text-[11px] text-[var(--ink3)]">{s.duration_ms} ms</span>}
              {s.at_utc && <span className="text-[11px] text-[var(--ink3)]">{new Date(s.at_utc).toLocaleTimeString()}</span>}
            </div>
            {s.detail && <div className="text-[12.5px] text-[var(--ink2)]">{s.detail}</div>}
          </motion.li>
        );
      })}
    </ol>
  );
}

/* ---------------- application-side progress (not model progress) ---------------- */
export function Progress({ stages, current }: { stages: string[]; current: number }) {
  return (
    <div className="soft p-3" aria-live="polite">
      <div className="mb-2 flex items-center justify-between text-[11px] text-[var(--ink3)]"><span className="eyebrow !text-[10px]">Workflow progress</span><span>application-side, not model progress</span></div>
      <div className="scanbar mb-3" />
      <ol className="grid gap-1.5 sm:grid-cols-2">
        {stages.map((s, i) => (
          <li key={s} className={`flex items-center gap-2 text-[13px] ${i < current ? 'text-[var(--good)]' : i === current ? 'font-semibold text-[var(--accent)]' : 'text-[var(--ink3)]'}`}>
            {i < current ? <CheckCircle2 size={14} /> : i === current ? <Hourglass size={14} className="animate-pulse" /> : <CircleDashed size={14} />} {s}
          </li>
        ))}
      </ol>
    </div>
  );
}

/* ---------------- small building blocks ---------------- */
export function Card({ icon: Icon, title, sub, children, className = '' }: { icon: LucideIcon; title: string; sub?: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={`panel flex flex-col ${className}`}>
      <div className="mb-3 flex items-center gap-2">
        <Icon size={16} className="text-[var(--accent)]" />
        <h3 className="text-[14px] font-semibold">{title}</h3>
        {sub && <span className="ml-auto truncate text-[11px] text-[var(--ink3)]">{sub}</span>}
      </div>
      {children}
    </section>
  );
}

export function Muted({ icon: Icon, text, tone }: { icon: LucideIcon; text: string; tone?: 'warn' }) {
  return <div className={`flex items-center gap-2 text-sm ${tone === 'warn' ? 'text-[var(--warn)]' : 'text-[var(--ink3)]'}`}><Icon size={16} /> {text}</div>;
}

