'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api, OUTCOME_STYLE } from '@/lib/api';
import { PageHeader } from '@/components/ui';
import { PAGE_ICON } from '@/lib/icons';

export default function CasesPage() {
  const [rows, setRows] = useState<any[] | null>(null);
  const [filter, setFilter] = useState('');
  const [error, setError] = useState('');
  const load = () => api('investigations?limit=200').then(setRows).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  async function remove(id: string) {
    if (!confirm('Delete this case and its findings? The audit trail keeps a "case.deleted" event.')) return;
    try {
      await api(`investigations/${id}`, { method: 'DELETE' });
      load();
    } catch (e: any) {
      setError(e.message);
    }
  }

  const shown = (rows ?? []).filter((r) => !filter || r.use_case === filter);
  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <PageHeader icon={PAGE_ICON.cases} title="Case history" subtitle="Every investigation, with deletion. Cases older than the retention period are purged automatically." />
        <select className="input" value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="">All use cases</option>
          <option value="family">Family & SIM</option>
          <option value="exam">Exam</option>
          <option value="insurance">Insurance</option>
          <option value="banking">Banking</option>
        </select>
      </header>
      {error && <p className="text-sm text-red-600">{error} <button className="btn ml-2" onClick={load}>Retry</button></p>}
      {rows === null ? (
        <p className="text-[var(--ink2)]">Loading…</p>
      ) : shown.length === 0 ? (
        <div className="panel text-sm text-[var(--ink2)]">No cases yet. Run a scenario from the dashboard or a module page.</div>
      ) : (
        <div className="panel overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-[var(--ink2)]">
              <tr><th>Case</th><th>Use case</th><th>Decision</th><th>When</th><th /></tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr key={r.id} className="border-t border-[var(--line)]">
                  <td className="py-1.5"><Link href={`/investigations/${r.id}`} className="text-blue-600 hover:underline">{r.title}</Link><div className="mono text-[var(--ink2)]">{r.id}</div></td>
                  <td><span className="chip">{r.use_case}</span></td>
                  <td><span className={`chip ${OUTCOME_STYLE[r.outcome]}`}>{r.outcome}</span></td>
                  <td className="text-xs text-[var(--ink2)]">{new Date(r.created_at * 1000).toLocaleString()}</td>
                  <td><button className="btn text-red-600" onClick={() => remove(r.id)}>Delete</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
