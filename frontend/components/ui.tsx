'use client';
import { useEffect, useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import { ExplainButton } from './Chat';

export function PageHeader({ icon: Icon, title, subtitle, explain, children }: { icon: LucideIcon; title: string; subtitle?: string; explain?: string; children?: React.ReactNode }) {
  return (
    <header className="mb-7 flex flex-wrap items-start justify-between gap-4 border-b-2 border-[var(--ink)] pb-5 fade-in">
      <div className="flex items-start gap-4">
        <div className="flex h-14 w-14 shrink-0 -rotate-3 items-center justify-center border-2 border-[var(--ink)] bg-[var(--hi)] text-[var(--ink)] shadow-[var(--shadow)]">
          <Icon size={26} />
        </div>
        <div>
          <h1 className="text-3xl md:text-5xl">{title}</h1>
          {subtitle && <p className="mt-2 max-w-3xl text-[15px] text-[var(--ink2)]">{subtitle}</p>}
        </div>
      </div>
      <div className="flex items-center gap-2">
        {children}
        {explain && <ExplainButton topic={explain} />}
      </div>
    </header>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: string; icon?: LucideIcon; count?: number }[]; value: T; onChange: (t: T) => void }) {
  return (
    <div className="tabs">
      {tabs.map(({ id, label, icon: Icon, count }) => (
        <button key={id} className={`tab ${value === id ? 'tab-active' : ''}`} onClick={() => onChange(id)}>
          {Icon && <Icon size={15} />} {label}
          {count !== undefined && <span className="rounded-full bg-slate-200/70 px-1.5 text-[11px]">{count}</span>}
        </button>
      ))}
    </div>
  );
}

export function Counter({ value, duration = 900 }: { value: number; duration?: number }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    let raf = 0;
    const start = performance.now();
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / duration);
      setN(Math.round(value * (1 - Math.pow(1 - p, 3))));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration]);
  return <>{n}</>;
}

export function SectionTitle({ icon: Icon, children, explain, data, right }: { icon?: LucideIcon; children: React.ReactNode; explain?: string; data?: any; right?: React.ReactNode }) {
  return (
    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
      <h3 className="flex items-center gap-2 font-semibold">
        {Icon && <span className="grid size-7 place-items-center border-2 border-[var(--ink)] bg-[var(--hi)]"><Icon size={15} /></span>} <span className="uppercase tracking-tight">{children}</span>
      </h3>
      <div className="flex items-center gap-2">
        {right}
        {explain && <ExplainButton topic={explain} data={data} />}
      </div>
    </div>
  );
}

export function Empty({ icon: Icon, title, hint }: { icon: LucideIcon; title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-none border-2 border-dashed border-[var(--ink)] p-10 text-center">
      <Icon size={32} className="mb-3 text-[var(--ink2)]" />
      <div className="font-medium">{title}</div>
      {hint && <div className="mt-1 text-sm text-[var(--ink2)]">{hint}</div>}
    </div>
  );
}
