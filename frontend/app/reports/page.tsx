'use client';
import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { motion } from 'motion/react';
import { PAGE_ICON } from '@/lib/icons';
import { ArrowDownUp, FlaskConical, Loader2, MonitorCheck, PlugZap, Search } from 'lucide-react';
import { api, CATEGORY_LABEL, STATUS } from '@/lib/api';
import { PageHeader } from '@/components/ui';
import { ErrorBanner, Skeleton, StatusPill } from '@/components/viz';
import { runFrontendSmoke } from '@/lib/smoke';

const STATUSES = ['PASS', 'FAIL', 'HOLD', 'ERROR', 'SKIPPED'];

export default function ReportsPage() {
  const [stats, setStats] = useState<any>(null);
  const [data, setData] = useState<any>(null);
  const [q, setQ] = useState('');
  const [status, setStatus] = useState('');
  const [category, setCategory] = useState('');
  const [provider, setProvider] = useState('');
  const [since, setSince] = useState('');
  const [sort, setSort] = useState('-created_at');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [last, setLast] = useState<string>('');

  const load = () => {
    const p = new URLSearchParams({ sort, limit: '200' });
    if (q) p.set('q', q);
    if (status) p.set('status', status);
    if (category) p.set('category', category);
    if (provider) p.set('provider_name', provider);
    if (since) p.set('since', String(new Date(since).getTime() / 1000));
    api(`reports?${p}`).then(setData).catch((e) => setError(e.message));
    api('reports/stats').then(setStats).catch(() => {});
  };
  useEffect(() => { const t = setTimeout(load, 200); return () => clearTimeout(t); }, [q, status, category, provider, since, sort]); // eslint-disable-line react-hooks/exhaustive-deps

  async function run(kind: 'connectivity' | 'selftest' | 'smoke') {
    setBusy(kind);
    setError('');
    try {
      const r = kind === 'smoke' ? await runFrontendSmoke() : await api(`reports/${kind}`, { method: 'POST' });
      setLast(r.report_id);
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy('');
    }
  }

  const providers = useMemo(() => Array.from(new Set((data?.items ?? []).map((r: any) => r.provider).filter(Boolean))) as string[], [data]);
  const total = stats?.total ?? 0;

  return (
    <div className="flex flex-col gap-5">
      <PageHeader icon={PAGE_ICON.reports} title="Test reports" subtitle="Every test leaves a persistent report — pass, fail, hold, error or skipped. A status reflects the test's acceptance criteria, never just an HTTP 200." />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Tile label="Total tests" value={stats ? total : null} color="var(--accent)" active={!status} onClick={() => setStatus('')} />
        {STATUSES.map((s) => (
          <Tile key={s} label={STATUS[s].label} value={stats ? stats.by_status[s] ?? 0 : null} color={STATUS[s].color} active={status === s} onClick={() => setStatus(status === s ? '' : s)}
            bar={total ? (stats.by_status[s] ?? 0) / total : 0} />
        ))}
      </div>

      <section className="panel flex flex-wrap items-center gap-2">
        <span className="mr-1 text-sm font-semibold">Run a test:</span>
        <button className="btn" disabled={!!busy} onClick={() => run('connectivity')}>{busy === 'connectivity' ? <Loader2 size={15} className="animate-spin" /> : <PlugZap size={15} />} API connectivity</button>
        <button className="btn" disabled={!!busy} onClick={() => run('selftest')}>{busy === 'selftest' ? <Loader2 size={15} className="animate-spin" /> : <FlaskConical size={15} />} Backend test suite</button>
        <button className="btn" disabled={!!busy} onClick={() => run('smoke')}>{busy === 'smoke' ? <Loader2 size={15} className="animate-spin" /> : <MonitorCheck size={15} />} Frontend integration</button>
        <span className="text-xs text-[var(--ink3)]">all free — no DetectifAI credits{busy === 'selftest' ? ' · running pytest (~40 s)…' : ''}</span>
        {last && <Link href={`/reports/${last}`} className="ml-auto text-sm font-semibold text-[var(--accent)] hover:underline">Open latest report →</Link>}
      </section>
      {error && <ErrorBanner error={error} />}

      <section className="panel !p-0">
        <div className="flex flex-wrap items-end gap-2 border-b border-[var(--line)] p-3">
          <label className="label min-w-[220px] flex-1">
            Search
            <span className="relative">
              <Search size={15} className="absolute left-2.5 top-2.5 text-[var(--ink3)]" />
              <input className="input w-full !pl-8" placeholder="Report ID, case ID, speaker ID or name" value={q} onChange={(e) => setQ(e.target.value)} />
            </span>
          </label>
          <label className="label">Feature
            <select className="input" value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">All features</option>
              {Object.entries(CATEGORY_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          <label className="label">Status
            <select className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All</option>
              {STATUSES.map((s) => <option key={s} value={s}>{STATUS[s].label}</option>)}
            </select>
          </label>
          <label className="label">Provider
            <select className="input" value={provider} onChange={(e) => setProvider(e.target.value)}>
              <option value="">Any</option>
              {providers.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </label>
          <label className="label">Since
            <input type="date" className="input" value={since} onChange={(e) => setSince(e.target.value)} />
          </label>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-[var(--ink2)]">
              <tr className="border-b border-[var(--line)]">
                {[['status', 'Status'], ['name', 'Test'], ['category', 'Feature'], ['', 'Outcome'], ['created_at', 'When'], ['duration_ms', 'Duration']].map(([k, l]) => (
                  <th key={l} className="px-3 py-2 font-semibold">
                    {k ? (
                      <button className="inline-flex items-center gap-1 hover:text-[var(--ink)]" onClick={() => setSort(sort === `-${k}` ? k : `-${k}`)}>
                        {l} <ArrowDownUp size={11} className={sort.replace('-', '') === k ? 'text-[var(--accent)]' : 'opacity-40'} />
                      </button>
                    ) : l}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {!data && [0, 1, 2, 3, 4].map((i) => <tr key={i}><td colSpan={6} className="px-3 py-2"><Skeleton className="h-8" /></td></tr>)}
              {data?.items.map((r: any, i: number) => (
                <motion.tr key={r.report_id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: Math.min(i, 15) * 0.02 }}
                  className="border-b border-[var(--line)] last:border-0 hover:bg-[var(--panel2)]">
                  <td className="px-3 py-2.5"><StatusPill status={r.status} /></td>
                  <td className="max-w-[340px] px-3 py-2.5">
                    <Link href={`/reports/${r.report_id}`} className="block truncate font-semibold hover:text-[var(--accent)]">{r.name}</Link>
                    <div className="mono truncate text-[var(--ink3)]">{r.report_id}{r.case_id ? ` · ${r.case_id}` : ''}{r.speaker_id ? ` · spk ${r.speaker_id}` : ''}</div>
                  </td>
                  <td className="px-3 py-2.5 text-[var(--ink2)]">{CATEGORY_LABEL[r.category] ?? r.category}</td>
                  <td className="max-w-[260px] px-3 py-2.5"><div className="truncate text-[13px]" title={r.summary}>{r.verification_outcome ? <b className="mr-1 text-[12px]">{r.verification_outcome.replaceAll('_', ' ')}</b> : null}{r.summary}</div></td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-[var(--ink2)]">{new Date(r.created_at * 1000).toLocaleString()}</td>
                  <td className="px-3 py-2.5 text-[var(--ink2)]">{r.duration_ms != null ? `${(r.duration_ms / 1000).toFixed(1)} s` : '—'}</td>
                </motion.tr>
              ))}
              {data && !data.items.length && <tr><td colSpan={6} className="p-8 text-center text-[var(--ink2)]">No reports match these filters.</td></tr>}
            </tbody>
          </table>
        </div>
        {data && <div className="border-t border-[var(--line)] px-3 py-2 text-xs text-[var(--ink3)]">{data.items.length} of {data.total} report(s)</div>}
      </section>
    </div>
  );
}

function Tile({ label, value, color, active, onClick, bar }: { label: string; value: number | null; color: string; active?: boolean; onClick?: () => void; bar?: number }) {
  return (
    <button onClick={onClick} className={`panel panel-hover !p-3.5 text-left ${active ? 'ring-2 ring-[var(--accent)]/30' : ''}`} aria-pressed={active}>
      <div className="text-xs font-medium text-[var(--ink2)]">{label}</div>
      {value === null ? <Skeleton className="mt-1 h-7 w-12" /> : <div className="text-2xl font-bold tabular-nums" style={{ color }}>{value}</div>}
      {bar !== undefined && <div className="mt-2 h-1 overflow-hidden rounded-none bg-[var(--panel2)]"><motion.div className="h-full rounded-none" style={{ background: color }} initial={{ width: 0 }} animate={{ width: `${bar * 100}%` }} /></div>}
    </button>
  );
}
