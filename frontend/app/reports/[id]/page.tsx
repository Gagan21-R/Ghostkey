'use client';
import { use, useEffect, useState } from 'react';
import Link from 'next/link';
import { motion } from 'motion/react';
import { ArrowLeft, CheckCircle2, ClipboardCheck, Download, FileInput, ListChecks, Printer, Stethoscope, Target, Wrench, XCircle } from 'lucide-react';
import { api, CATEGORY_LABEL, STATUS } from '@/lib/api';
import { Card, ErrorBanner, Skeleton, StatusPill, Timeline } from '@/components/viz';

export default function ReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let stop = false;
    const load = () => api(`reports/${id}`).then((x) => {
      if (stop) return;
      setR(x);
      if (x.status === 'RUNNING') setTimeout(load, 1200); // steps appear as execution events arrive
    }).catch((e) => setError(e.message));
    load();
    return () => { stop = true; };
  }, [id]);

  if (error) return <ErrorBanner error={error} />;
  if (!r) return <div className="flex flex-col gap-4"><Skeleton className="h-28" /><Skeleton className="h-64" /></div>;
  const st = STATUS[r.status] ?? STATUS.SKIPPED;
  const a = r.assessment ?? {};
  const dg = r.diagnostics ?? {};
  const ev = r.evidence ?? {};

  return (
    <div className="flex flex-col gap-4">
      <div className="no-print flex flex-wrap items-center justify-between gap-2">
        <Link href="/reports" className="btn btn-ghost"><ArrowLeft size={15} /> All reports</Link>
        <div className="flex gap-2">
          <a className="btn" href={`/api/reports/${id}/export`} download={`ghostkey-report-${id}.json`}><Download size={15} /> Download JSON</a>
          <button className="btn" onClick={() => window.print()}><Printer size={15} /> Print / PDF</button>
        </div>
      </div>

      {/* final assessment */}
      <motion.section initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="panel relative overflow-hidden">
        <div className="absolute inset-x-0 top-0 h-1" style={{ background: st.color }} />
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="eyebrow">{CATEGORY_LABEL[r.test.category] ?? r.test.category} · test report</div>
            <h1 className="mt-1 text-xl font-bold md:text-2xl">{r.test.name}</h1>
            <p className="mt-1 text-[15px] font-semibold text-[var(--ink)]">{a.summary ?? (r.status === 'RUNNING' ? 'Running…' : '')}</p>
          </div>
          <div className="flex flex-col items-end gap-2">
            <StatusPill status={r.status} size="md" />
            {r.verification_outcome && <span className="chip">outcome: {r.verification_outcome.replaceAll('_', ' ')}</span>}
            <span className="chip">execution: {r.execution_status}</span>
          </div>
        </div>
        <div className="mt-4 grid gap-2 text-[12.5px] sm:grid-cols-2 lg:grid-cols-4">
          <KV k="Report ID" v={r.report_id} mono />
          <KV k="Case ID" v={r.ids?.case_id} mono />
          <KV k="Correlation ID" v={r.ids?.correlation_id} mono />
          <KV k="Attempt / speaker" v={[r.ids?.attempt_id, r.ids?.speaker_id].filter(Boolean).join(' · ')} mono />
          <KV k="Started (local)" v={r.timestamps.started_at_utc && new Date(r.timestamps.started_at_utc).toLocaleString()} />
          <KV k="Started (UTC)" v={r.timestamps.started_at_utc} mono />
          <KV k="Duration" v={r.timestamps.duration_ms != null ? `${r.timestamps.duration_ms} ms` : '—'} />
          <KV k="Environment" v={`${r.test.environment} · v${r.test.app_version}${r.test.git_commit ? ` · ${r.test.git_commit}` : ''}`} />
        </div>
        <p className="mt-3 text-[12px] text-[var(--ink3)]">
          Status basis: <b>{(a.status_basis ?? '—').replaceAll('_', ' ')}</b>. PASS means the acceptance criteria below were met — an HTTP 200 alone never counts.
        </p>
      </motion.section>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card icon={Target} title="Expected vs actual">
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="soft p-3"><div className="eyebrow mb-1 !text-[10px]">Expected</div>{r.expected?.description ?? (r.expected ? JSON.stringify(r.expected) : 'not declared')}</div>
            <div className="soft p-3"><div className="eyebrow mb-1 !text-[10px]">Actual</div>{r.actual ? (typeof r.actual === 'string' ? r.actual : <Pairs obj={r.actual} />) : r.verification_outcome ?? '—'}</div>
          </div>
          <div className="mt-3 flex flex-col gap-1.5">
            {(a.acceptance_criteria ?? []).map((c: any, i: number) => (
              <div key={i} className={`flex items-start gap-2 rounded-none border px-3 py-2 text-[13px] ${c.satisfied ? 'st-pass' : 'st-fail'}`}>
                {c.satisfied ? <CheckCircle2 size={15} className="mt-0.5 shrink-0" /> : <XCircle size={15} className="mt-0.5 shrink-0" />}
                <span className="min-w-0 flex-1 text-[var(--ink)]">{String(c.criterion).replaceAll('_', ' ')}</span>
                <span className="mono shrink-0 truncate text-[var(--ink2)]" title={JSON.stringify(c.actual)}>{typeof c.actual === 'object' ? JSON.stringify(c.actual) : String(c.actual ?? '')}</span>
              </div>
            ))}
            {!(a.acceptance_criteria ?? []).length && <span className="text-sm text-[var(--ink3)]">No acceptance criteria recorded.</span>}
          </div>
        </Card>

        <Card icon={FileInput} title="Inputs">
          {(r.inputs ?? []).length === 0 && <span className="text-sm text-[var(--ink3)]">No file inputs.</span>}
          {(r.inputs ?? []).map((inp: any, i: number) => (
            <div key={i} className="soft mb-2 grid grid-cols-2 gap-x-3 gap-y-1 p-3 text-[12.5px]">
              {Object.entries(inp).map(([k, v]) => <KV key={k} k={k.replaceAll('_', ' ')} v={v == null ? '—' : String(v)} mono={k === 'sha256'} />)}
            </div>
          ))}
          <div className="mt-1 text-[12px] text-[var(--ink3)]">Endpoint: <span className="mono">{r.execution.endpoint ?? '—'}</span> · provider: {r.execution.provider ?? '—'}</div>
          {r.execution.request_ids?.length > 0 && <div className="mono mt-1 text-[var(--ink3)]">request IDs: {r.execution.request_ids.join(', ')}</div>}
        </Card>
      </div>

      <Card icon={ListChecks} title="Execution timeline" sub={`${r.execution.steps.length} step(s)${r.status === 'RUNNING' ? ' · updating live' : ''}`}>
        <Timeline steps={r.execution.steps} />
        {r.execution.agents?.length > 0 && (
          <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {r.execution.agents.map((ag: any) => (
              <div key={ag.agent} className="soft p-2.5 text-[12.5px]">
                <div className="flex items-center justify-between gap-2"><b>{ag.agent.replaceAll('_', ' ')}</b><span className="chip">{ag.execution_status}</span></div>
                <div className="font-semibold text-[var(--accent)]">{ag.status.replaceAll('_', ' ').toLowerCase()}</div>
                <div className="line-clamp-2 text-[var(--ink2)]">{ag.summary}</div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card icon={ClipboardCheck} title="Evidence">
        <div className="grid gap-3 md:grid-cols-2">
          {Object.entries(ev).filter(([, v]) => v != null && !(Array.isArray(v) && !v.length)).map(([k, v]) => (
            <details key={k} className="soft p-3 text-[12.5px]" open={['speaker_result', 'provider_result', 'policy', 'deepfake_result'].includes(k)}>
              <summary className="cursor-pointer font-semibold capitalize">{k.replaceAll('_', ' ')}</summary>
              <div className="mt-2">{typeof v === 'object' ? <Pairs obj={v} /> : String(v)}</div>
            </details>
          ))}
        </div>
      </Card>

      <Card icon={Stethoscope} title="Diagnostics">
        <div className="grid gap-2 text-[13px] sm:grid-cols-2">
          <KV k="Failure stage" v={dg.failure_stage ?? 'none'} />
          <KV k="Root cause (confirmed)" v={dg.root_cause ?? 'not determined'} />
          <KV k="Retry eligible" v={dg.retry_eligible == null ? '—' : dg.retry_eligible ? 'yes' : 'no'} />
          <KV k="Recommended next step" v={dg.recommended_next_step ?? '—'} />
        </div>
        {dg.hypotheses?.length > 0 && (
          <div className="mt-3 rounded-none border border-[#f3d9a8] bg-[var(--warn-soft)] p-3 text-[13px]">
            <div className="mb-1 flex items-center gap-1.5 font-semibold text-[var(--warn)]"><Wrench size={14} /> Possible causes (hypotheses, not confirmed)</div>
            <ul className="list-disc pl-5">{dg.hypotheses.map((h: string, i: number) => <li key={i}>{h}</li>)}</ul>
          </div>
        )}
        {dg.errors?.length > 0 && <ul className="mt-3 list-disc pl-5 text-[13px] text-[var(--bad)]">{dg.errors.map((e: any, i: number) => <li key={i}><b>{e.stage}:</b> {e.message}</li>)}</ul>}
        {dg.technical && (
          <details className="mt-3 text-[12px]">
            <summary className="cursor-pointer font-medium text-[var(--accent)]">Technical details (developers)</summary>
            <pre className="mono mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded-none bg-[var(--panel2)] p-3">{dg.technical}</pre>
          </details>
        )}
      </Card>
    </div>
  );
}

function KV({ k, v, mono }: { k: string; v: any; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <div className="text-[10.5px] font-semibold uppercase tracking-wide text-[var(--ink3)]">{k}</div>
      <div className={`truncate ${mono ? 'mono' : ''}`} title={v ? String(v) : ''}>{v || '—'}</div>
    </div>
  );
}

function Pairs({ obj }: { obj: any }) {
  if (Array.isArray(obj)) return <ul className="list-disc pl-4">{obj.slice(0, 20).map((x, i) => <li key={i}>{typeof x === 'object' ? JSON.stringify(x) : String(x)}</li>)}</ul>;
  return (
    <div className="grid gap-1">
      {Object.entries(obj ?? {}).filter(([, v]) => v !== null && v !== undefined).map(([k, v]) => (
        <div key={k} className="grid grid-cols-[130px_1fr] gap-2">
          <span className="text-[var(--ink3)]">{k.replaceAll('_', ' ')}</span>
          <span className="mono break-all">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</span>
        </div>
      ))}
    </div>
  );
}
