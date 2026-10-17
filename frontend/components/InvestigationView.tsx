'use client';
import { useEffect, useState } from 'react';
import {
  AlertTriangle, Bot, Brain, CheckCircle2, ClipboardList, Cpu, Fingerprint, GitBranch, Hourglass, Layers, ListChecks,
  MessagesSquare, Radio, Scale, ShieldAlert, ShieldCheck, ShieldX, Smartphone, Swords, Umbrella, UserSearch, XCircle,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { ExplainButton } from './Chat';
import { SectionTitle, Tabs } from './ui';
import { AgentPipeline, Card, EvidenceCards, ResultHero, RiskScale, SpeakerCompare, VoiceMeter } from './viz';

export const SOURCE_LABEL: Record<string, [string, string]> = {
  live_provider: ['Real DetectifAI output', 'text-teal-700 border-emerald-500/40'],
  simulated_fixture: ['SIMULATED', 'text-amber-700 border-amber-500/40'],
  local_face_model: ['Local face model', 'text-blue-600 border-sky-500/40'],
  structured_case_data: ['Case data · rule-based', 'text-violet-600 border-violet-500/40'],
  session_service: ['Session service', 'text-blue-600 border-sky-500/40'],
  none: ['No evidence', 'text-[var(--ink2)]'],
};

const AGENT: Record<string, { label: string; icon: LucideIcon; color: string }> = {
  voice_authenticity_agent: { label: 'Voice Authenticity', icon: Radio, color: '#0891b2' },
  speaker_identity_agent: { label: 'Speaker Identity', icon: Fingerprint, color: '#2563eb' },
  exam_identity_agent: { label: 'Exam Identity', icon: UserSearch, color: '#0284c7' },
  sim_risk_agent: { label: 'SIM & Lifecycle', icon: Smartphone, color: '#db2777' },
  contextual_risk_agent: { label: 'Contextual Risk', icon: Scale, color: '#d97706' },
  insurance_claim_agent: { label: 'Insurance Claim', icon: Umbrella, color: '#7c3aed' },
  adversarial_critic: { label: 'Adversarial Critic', icon: Swords, color: '#e11d48' },
  evidence_reconciler: { label: 'Evidence Reconciler', icon: GitBranch, color: '#0d9488' },
  policy_engine: { label: 'Policy Engine', icon: ShieldCheck, color: '#2563eb' },
  detectify_provider: { label: 'DetectifAI', icon: Cpu, color: '#0891b2' },
  session_service: { label: 'Session service', icon: Hourglass, color: '#0284c7' },
  face_service: { label: 'Face model (OpenCV)', icon: UserSearch, color: '#0284c7' },
  simulated_carrier: { label: 'Carrier (simulated)', icon: Smartphone, color: '#db2777' },
  orchestrator: { label: 'Orchestrator', icon: Layers, color: '#64748b' },
};

const STEP_STYLE: Record<string, string> = {
  input: '#64748b', provider: '#0891b2', face_model: '#0284c7', carrier_event: '#db2777', session: '#0284c7', finding: '#2563eb',
  challenge: '#e11d48', response: '#d97706', critic: '#e11d48', reconcile: '#0d9488', policy: '#7c3aed',
};

type TabId = 'verdict' | 'agents' | 'debate' | 'timeline' | 'evidence';

function FaceSummary({ rec }: { rec: any }) {
  const frames = rec.request?.face_frames ?? [];
  const thr = rec.request?.face_model?.threshold ?? 0.363;
  const face = rec.findings.find((f: any) => f.finding_type === 'exam_identity');
  return (
    <Card icon={UserSearch} title="Face verification" sub={rec.request?.face_model?.name ?? 'local face model'} className="lg:col-span-2">
      <div className="mb-3 text-[15px] font-semibold capitalize" style={{ color: face?.status === 'FACE_MATCH_SUPPORTED' ? 'var(--good)' : face?.status?.includes('MISMATCH') || face?.status === 'MULTIPLE_FACES_DETECTED' ? 'var(--bad)' : 'var(--warn)' }}>
        {(face?.status ?? 'no result').replaceAll('_', ' ').toLowerCase()}
      </div>
      <div className="flex flex-wrap items-end gap-2">
        {frames.map((f: any, i: number) => {
          const sim = f.best_similarity;
          const ok = typeof sim === 'number' && sim >= thr;
          return (
            <div key={i} className="flex w-14 flex-col items-center gap-1 text-[10.5px] text-[var(--ink3)]">
              <div className="relative h-20 w-6 overflow-hidden rounded-none bg-[var(--panel2)]">
                {typeof sim === 'number' && <div className="absolute inset-x-0 bottom-0 rounded-none" style={{ height: `${Math.max(4, Math.min(1, sim) * 100)}%`, background: ok ? 'var(--good)' : 'var(--bad)' }} />}
                <div className="absolute inset-x-0 border-t-2 border-dashed border-[var(--ink)]" style={{ bottom: `${thr * 100}%` }} />
              </div>
              <span>frame {i + 1}</span>
              <span className="font-semibold" style={{ color: typeof sim === 'number' ? (ok ? 'var(--good)' : 'var(--bad)') : 'var(--ink3)' }}>{typeof sim === 'number' ? sim.toFixed(2) : `${f.faces ?? 0} face`}</span>
            </div>
          );
        })}
      </div>
      <div className="mt-2 text-[11px] text-[var(--ink3)]">dashed line = cosine threshold {thr} · face similarity never proves liveness</div>
    </Card>
  );
}

export default function InvestigationView({ rec }: { rec: any }) {
  const [tab, setTab] = useState<TabId>('verdict');
  useEffect(() => setTab('verdict'), [rec.investigation_id]);
  const d = rec.decision;
  const req = rec.request ?? {};
  const find = (t: string) => rec.findings.find((f: any) => f.finding_type === t);
  const speaker = find('speaker_identity');
  const isExam = rec.use_case === 'exam';
  return (
    <div className="flex flex-col gap-4 fade-in">
      <ResultHero outcome={d.outcome} headline={d.headline || d.reasons.at(-1)} kind="Final security policy decision" title={rec.title} at={rec.created_at} reportId={rec.report_id}>
        {rec.expected_outcome && <span className="chip">expected: {rec.expected_outcome.replaceAll('_', ' ').toLowerCase()}</span>}
        <span className={`chip ${rec.simulated_inputs ? 'st-hold' : 'st-pass'}`}>{rec.simulated_inputs ? 'includes simulated inputs' : 'live inputs'}</span>
        <ExplainButton topic="decision" data={rec} label="Why?" />
      </ResultHero>

      <div className="grid gap-4 lg:grid-cols-3">
        {isExam ? <FaceSummary rec={rec} /> : (
          <>
            <VoiceMeter p={req.audio_authenticity} />
            <SpeakerCompare claimed={req.claimed_identity} speakerId={req.speaker_verification?.details?.speaker_id} p={req.speaker_verification}
              findingStatus={speaker?.status === 'NO_REFERENCE' ? undefined : speaker?.status} />
          </>
        )}
        <RiskScale status={find('action_risk')?.status} />
      </div>

      <AgentPipeline rec={rec} />
      <EvidenceCards rec={rec} />

      <section className="panel">
        <div className="eyebrow mb-1">Why this decision</div>
        <div className="text-[17px] font-semibold">{d.headline || d.reasons.at(-1)}</div>
        <details className="mt-2 text-sm text-[var(--ink2)]">
          <summary className="cursor-pointer select-none font-medium text-[var(--accent)]">Supporting evidence ({d.reasons.length} reason{d.reasons.length === 1 ? '' : 's'}, {d.rules_fired.length} rule{d.rules_fired.length === 1 ? '' : 's'})</summary>
          <ul className="mt-2 list-disc space-y-1 pl-5">{d.reasons.map((r: string, i: number) => <li key={i}>{r}</li>)}</ul>
          <div className="mt-2 flex flex-wrap gap-1.5">{d.rules_fired.map((r: string) => <span key={r} className="chip">{r}</span>)}</div>
          <div className="mono mt-2 text-[var(--ink3)]">case {rec.case_id ?? rec.investigation_id} · correlation {rec.correlation_id ?? '—'}{rec.report_id ? ` · report ${rec.report_id}` : ''}</div>
        </details>
      </section>

      <div className="eyebrow mt-2">Technical details</div>
      <Tabs<TabId>
        value={tab}
        onChange={setTab}
        tabs={[
          { id: 'verdict', label: 'Requirements', icon: ListChecks },
          { id: 'agents', label: 'Agents', icon: Bot, count: rec.findings.length },
          { id: 'debate', label: 'Critic debate', icon: MessagesSquare, count: rec.challenges.length },
          { id: 'timeline', label: 'Timeline', icon: ClipboardList, count: rec.timeline.length },
          { id: 'evidence', label: 'Evidence', icon: Brain },
        ]}
      />

      {tab === 'verdict' && (
        <section className="panel fade-in">
          <SectionTitle icon={ListChecks} explain="requirements" data={rec}>Policy requirements</SectionTitle>
          <div className="grid gap-2 md:grid-cols-2 stagger">
            {d.requirements.map((r: any) => (
              <div key={r.name} className={`flex items-start gap-3 rounded-none border p-3 text-sm ${r.satisfied ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-rose-500/30 bg-rose-500/5'}`}>
                {r.satisfied ? <CheckCircle2 size={18} className="mt-0.5 shrink-0 text-teal-700" /> : <XCircle size={18} className="mt-0.5 shrink-0 text-red-600" />}
                <div>
                  <div className="font-medium">{r.name.replaceAll('_', ' ')}</div>
                  <div className="text-[var(--ink2)]">{r.detail}</div>
                </div>
              </div>
            ))}
          </div>
          {d.rules_fired.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-1.5">
              {d.rules_fired.map((r: string) => <span key={r} className="chip">{r}</span>)}
            </div>
          )}
        </section>
      )}

      {tab === 'agents' && (
        <section className="fade-in">
          <SectionTitle icon={Bot} explain="agents" right={<ExplainButton topic="sources" label="Badges" />}>Agent findings</SectionTitle>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3 stagger">
            {rec.findings.map((f: any) => {
              const A = AGENT[f.agent] ?? { label: f.agent, icon: Bot, color: '#64748b' };
              const orig = rec.original_findings.find((o: any) => o.finding_id === f.finding_id);
              const src = SOURCE_LABEL[f.evidence_source];
              return (
                <div key={f.finding_id} className="panel panel-hover !p-4 text-sm">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <div className="flex h-9 w-9 items-center justify-center rounded-none" style={{ background: `${A.color}22`, color: A.color }}><A.icon size={18} /></div>
                      <div>
                        <div className="font-semibold">{A.label}</div>
                        <div className="mono text-[var(--ink2)]">v{f.agent_version} · {f.execution_status}</div>
                      </div>
                    </div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    <span className="chip text-[var(--ink)]">{f.status.replaceAll('_', ' ')}</span>
                    {src && <span className={`chip ${src[1]}`}>{src[0]}</span>}
                    {f.revision > 0 && <span className="chip text-amber-700">revised · was {orig?.status?.replaceAll('_', ' ').toLowerCase()}</span>}
                  </div>
                  <ul className="mt-3 space-y-1 text-[13px] text-[var(--ink)]/90">
                    {f.observations.slice(0, 4).map((o: string, i: number) => <li key={i} className="flex gap-2"><span className="text-blue-600">›</span>{o}</li>)}
                  </ul>
                  {f.recommended_next_step && <div className="mt-3 rounded-none bg-sky-500/10 px-3 py-2 text-[12.5px] text-blue-700">→ {f.recommended_next_step}</div>}
                  {f.contradictions.length > 0 && <div className="mt-2 flex gap-2 text-[12.5px] text-amber-700"><AlertTriangle size={14} className="mt-0.5 shrink-0" />{f.contradictions.join(' ')}</div>}
                  {f.errors?.length > 0 && <div className="mt-2 text-[12px] text-red-600">errors: {f.errors.join(' ')}</div>}
                  <details className="mt-2 text-[11.5px] text-[var(--ink2)]">
                    <summary className="cursor-pointer">limitations & evidence</summary>
                    <ul className="mt-1 list-disc pl-4">{f.limitations.map((l: string, i: number) => <li key={i}>{l}</li>)}</ul>
                    <div className="mono mt-1 break-all">{f.evidence_refs.join(' · ')}</div>
                  </details>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {tab === 'debate' && (
        <section className="panel fade-in">
          <SectionTitle icon={Swords} explain="critic" data={rec}>Adversarial critic debate</SectionTitle>
          {rec.challenges.length === 0 && <p className="text-sm text-[var(--ink2)]">The critic found nothing to challenge.</p>}
          <div className="space-y-4 stagger">
            {rec.challenges.map((c: any) => {
              const A = AGENT[c.target_agent] ?? { label: c.target_agent, icon: Bot, color: '#64748b' };
              return (
                <div key={c.challenge_id} className="space-y-2">
                  <div className="flex items-start gap-2.5">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-rose-500/15 text-red-600"><Swords size={15} /></div>
                    <div className="max-w-[85%] rounded-none rounded-none border border-rose-500/25 bg-rose-500/5 px-3.5 py-2.5 text-sm">
                      <div className="mb-0.5 text-[11px] text-red-600">Critic → {A.label} · round {c.round}</div>{c.question}
                    </div>
                  </div>
                  <div className="flex items-start justify-end gap-2.5">
                    <div className="max-w-[85%] rounded-none rounded-none border-2 border-[var(--ink)] bg-[var(--panel2)] px-3.5 py-2.5 text-sm">
                      <div className="mb-0.5 flex items-center gap-2 text-[11px]" style={{ color: A.color }}>
                        {A.label} <span className={`chip !py-0 ${c.outcome === 'revised' ? 'text-amber-700' : c.outcome === 'retracted' ? 'text-red-600' : 'text-teal-700'}`}>{c.outcome}</span>
                      </div>{c.response}
                    </div>
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full" style={{ background: `${A.color}22`, color: A.color }}><A.icon size={15} /></div>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-6 rounded-none border border-amber-500/25 bg-amber-500/5 p-4">
            <div className="mb-1 flex items-center gap-2 text-sm font-semibold text-amber-800"><AlertTriangle size={15} /> Unresolved disagreements (kept visible)</div>
            {rec.reconciliation.disagreements.length ? (
              <ul className="list-disc pl-5 text-sm text-amber-800/90">{rec.reconciliation.disagreements.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul>
            ) : <p className="text-sm text-[var(--ink2)]">None — the agents' findings are consistent.</p>}
          </div>
        </section>
      )}

      {tab === 'timeline' && (
        <section className="panel fade-in">
          <SectionTitle icon={ClipboardList} explain="timeline">Investigation timeline</SectionTitle>
          <ol className="relative ml-3 border-l-2 border-[var(--line)] stagger">
            {rec.timeline.map((e: any, i: number) => {
              const A = AGENT[e.actor] ?? { label: e.actor, icon: Bot, color: '#64748b' };
              const color = STEP_STYLE[e.step] ?? '#64748b';
              return (
                <li key={i} className="mb-4 ml-6">
                  <span className="absolute -left-[17px] flex h-8 w-8 items-center justify-center rounded-full border-2 bg-[var(--panel)]" style={{ borderColor: color, color }}>
                    <A.icon size={14} />
                  </span>
                  <div className="rounded-none border-2 border-[var(--ink)] bg-[var(--panel2)] px-4 py-2.5">
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <span className="mono text-[var(--ink2)]">+{e.t.toFixed(3)}s</span>
                      <span className="chip" style={{ color, borderColor: `${color}55` }}>{e.step.replace('_', ' ')}</span>
                      <b className="text-[13px]">{A.label}</b>
                    </div>
                    <div className="mt-1 text-sm text-[var(--ink)]/90">{e.detail}</div>
                  </div>
                </li>
              );
            })}
          </ol>
        </section>
      )}

      {tab === 'evidence' && (
        <section className="panel fade-in">
          <SectionTitle icon={Brain} explain="evidence">Evidence summary</SectionTitle>
          <div className="grid gap-3 md:grid-cols-3">
            {[
              ['Observed facts', rec.reconciliation.observed_facts.map((x: any) => (x.fact ? `${x.source}: ${x.fact}` : `${x.source}: ${x.status}${x.classification ? ` · ${x.classification}` : ''}${x.simulated ? ' · SIMULATED' : ''}`)), '#0d9488'],
              ['Model predictions', rec.reconciliation.model_predictions.map((x: any) => `${(AGENT[x.source]?.label ?? x.source)}: ${x.status}`), '#0891b2'],
              ['Hypotheses', rec.reconciliation.hypotheses.map((x: any) => `${(AGENT[x.source]?.label ?? x.source)}: ${x.status}`), '#7c3aed'],
            ].map(([title, items, color]: any) => (
              <div key={title} className="rounded-none border-2 border-[var(--ink)] bg-[var(--panel2)] p-3">
                <div className="mb-2 text-sm font-semibold" style={{ color }}>{title}</div>
                {items.length ? items.map((t: string, i: number) => <div key={i} className="mb-1.5 text-[12.5px] text-[var(--ink)]/85">• {t}</div>) : <div className="text-[12.5px] text-[var(--ink2)]">none</div>}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
