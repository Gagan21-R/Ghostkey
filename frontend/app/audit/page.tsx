'use client';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { PageHeader } from '@/components/ui';
import { PAGE_ICON } from '@/lib/icons';

export default function AuditPage() {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    api('audit').then(setData);
  }, []);
  if (!data) return <p className="text-[var(--ink2)]">Loading…</p>;
  return (
    <div className="flex flex-col gap-4">
      <PageHeader icon={PAGE_ICON.audit} title="Audit trail" explain="session" subtitle="Append-only log: every event is hash-chained to the previous one, so any edit is detectable." />
      <span className={`chip w-fit ${data.integrity.ok ? 'text-teal-700' : 'text-red-600'}`}>
        {data.integrity.ok ? `✓ hash chain intact · ${data.integrity.count} events` : `✗ chain broken at #${data.integrity.broken_at}`}
      </span>
      <div className="panel overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-[var(--ink2)]">
            <tr>
              <th>#</th>
              <th>Time</th>
              <th>Event</th>
              <th>Subject</th>
              <th>Details</th>
              <th>Hash</th>
            </tr>
          </thead>
          <tbody>
            {data.events.map((e: any) => (
              <tr key={e.seq} className="border-t border-[var(--line)] align-top">
                <td className="py-1.5 pr-2">{e.seq}</td>
                <td className="pr-2 text-xs">{new Date(e.at * 1000).toLocaleTimeString()}</td>
                <td className="pr-2">
                  <span className="chip">{e.event}</span>
                </td>
                <td className="mono pr-2">{e.subject}</td>
                <td className="mono max-w-md truncate pr-2" title={JSON.stringify(e.payload)}>
                  {JSON.stringify(e.payload)}
                </td>
                <td className="mono text-[var(--ink2)]">{e.hash.slice(0, 12)}…</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
