'use client';
import { useEffect, useRef, useState } from 'react';
import { Hourglass, Loader2, Play, ShieldAlert, ShieldCheck, ShieldX } from 'lucide-react';
import { api } from '@/lib/api';
import { PAGE_ICON } from '@/lib/icons';
import InvestigationView from '@/components/InvestigationView';
import { PageHeader, Tabs } from '@/components/ui';

const USE_CASES = [
  { id: 'family', title: 'Family & SIM', icon: PAGE_ICON.family },
  { id: 'exam', title: 'Exam identity', icon: PAGE_ICON.exam },
  { id: 'insurance', title: 'Insurance claims', icon: PAGE_ICON.insurance },
  { id: 'banking', title: 'Banking', icon: PAGE_ICON.banking },
];
const OUTCOMES = [
  { id: 'VERIFIED_AND_AUTHORIZED', label: 'Verified', icon: ShieldCheck, color: 'var(--good)' },
  { id: 'HOLD_FOR_VERIFICATION', label: 'Held', icon: Hourglass, color: 'var(--warn)' },
  { id: 'ESCALATED_FOR_REVIEW', label: 'Escalated', icon: ShieldAlert, color: 'var(--warn)' },
  { id: 'DENIED', label: 'Denied', icon: ShieldX, color: 'var(--bad)' },
];

export default function ScenarioLabPage() {
  const [scenarios, setScenarios] = useState<any[]>([]);
  const [result, setResult] = useState<any>(null);
  const [busy, setBusy] = useState('');
  const [live, setLive] = useState(false);
  const [uc, setUc] = useState('family');
  const [error, setError] = useState('');
  const anchor = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api('scenarios').then(setScenarios).catch((e) => setError(e.message));
  }, []);

  async function run(id: string) {
    setBusy(id);
    setError('');
    try {
      setResult(await api(`scenarios/${id}/run?live=${live}`, { method: 'POST' }));
      setTimeout(() => anchor.current?.scrollIntoView({ behavior: 'smooth' }), 80);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy('');
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader icon={PAGE_ICON.scenarios} title="Scenario lab" explain="sources" subtitle="17 scripted scenarios with expected outcomes." />
      <section>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <Tabs value={uc} onChange={setUc} tabs={USE_CASES.map((u) => ({ id: u.id, label: u.title, icon: u.icon, count: scenarios.filter((s) => s.use_case === u.id).length }))} />
          <label className="flex items-center gap-2 text-xs text-[var(--ink2)]"><input type="checkbox" checked={live} onChange={(e) => setLive(e.target.checked)} /> Scenario E uses live DetectifAI (2 checks)</label>
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3 stagger" key={uc}>
          {scenarios.filter((s) => s.use_case === uc).map((s) => {
            const O = OUTCOMES.find((o) => o.id === s.expected)!;
            return (
              <button key={s.id} onClick={() => run(s.id)} disabled={!!busy} className="panel panel-hover flex items-start gap-3 !p-4 text-left">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center border-2 border-[var(--ink)] bg-[var(--hi)] font-bold">{s.id}</div>
                <div className="flex-1">
                  <div className="text-sm font-semibold leading-snug">{s.title.replace(/^Insurance: |^Family: /, '')}</div>
                  <div className="mt-2 flex items-center gap-1.5 text-[11.5px]" style={{ color: O.color }}><O.icon size={13} /> expected: {O.label}</div>
                </div>
                {busy === s.id ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} className="text-[var(--ink2)]" />}
              </button>
            );
          })}
        </div>
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      </section>
      <div ref={anchor} className="scroll-mt-6">{result && <InvestigationView rec={result} />}</div>
    </div>
  );
}
