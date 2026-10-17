'use client';
import type { LucideIcon } from 'lucide-react';
import { ExplainButton } from './Chat';

/** Region page header (brutalist block + marquee band). */
export default function RegionHero({ region, icon: Icon, title, subtitle, explain }: {
  region: 'voice' | 'scenario'; icon: LucideIcon; title: string; subtitle?: string; explain?: string;
}) {
  const label = region === 'voice' ? 'Voice tools' : 'Use case';
  return (
    <>
      <header className="mb-7 border-2 border-[var(--ink)] bg-[var(--panel)] shadow-[var(--shadow-lg)] fade-in">
        <div className="flex flex-wrap items-center justify-between gap-4 p-6 md:p-8">
          <div className="flex max-w-4xl items-start gap-5">
            <div className="flex h-16 w-16 shrink-0 -rotate-3 items-center justify-center border-2 border-[var(--ink)] bg-[var(--hi)] text-[var(--ink)] shadow-[var(--shadow)] transition-transform hover:rotate-3">
              <Icon size={30} />
            </div>
            <div>
              <div className="eyebrow">/// {label}</div>
              <h1 className="mt-1 text-3xl md:text-6xl">{title}</h1>
              {subtitle && <p className="mt-3 max-w-3xl text-[15px] text-[var(--ink2)]">{subtitle}</p>}
            </div>
          </div>
          <div className="flex flex-col items-end gap-2">
            {explain && <ExplainButton topic={explain} />}
          </div>
        </div>
        <div className="marquee" aria-hidden="true">
          <div className="marquee-track">
            {[0, 1].map((k) => (
              <div key={k} className="flex">
                {Array.from({ length: 6 }, (_, i) => (
                  <span key={i} className="marquee-item">{title} <span className="text-[var(--hi)]">✦</span> {label} <span className="text-[var(--hi)]">✦</span></span>
                ))}
              </div>
            ))}
          </div>
        </div>
      </header>
    </>
  );
}
