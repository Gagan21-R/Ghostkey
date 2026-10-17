'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion } from 'motion/react';
import ThemeToggle from './ThemeToggle';
import Ghost from './Ghost';
import { PAGE_ICON as I } from '@/lib/icons';

const GROUPS = [
  { label: 'Overview', items: [{ href: '/', label: 'Command center', icon: I.dashboard }, { href: '/scenarios', label: 'Scenario lab', icon: I.scenarios }] },
  {
    label: 'Use cases',
    items: [
      { href: '/family', label: 'Family & SIM', icon: I.family },
      { href: '/exam', label: 'Exam identity', icon: I.exam },
      { href: '/insurance', label: 'Insurance claims', icon: I.insurance },
      { href: '/banking', label: 'Banking', icon: I.banking },
    ],
  },
  {
    label: 'Voice tools',
    items: [
      { href: '/voice', label: 'Voice analysis', icon: I.voice },
      { href: '/speakers', label: 'Speaker verification', icon: I.speakers },
    ],
  },
  {
    label: 'Records',
    items: [
      { href: '/reports', label: 'Test reports', icon: I.reports },
      { href: '/cases', label: 'Case history', icon: I.cases },
      { href: '/audit', label: 'Audit trail', icon: I.audit },
      { href: '/settings', label: 'Settings', icon: I.settings },
    ],
  },
];

export default function Nav() {
  const path = usePathname();
  const active = (href: string) => (href === '/' ? path === '/' : path.startsWith(href));
  return (
    <>
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r-2 border-[var(--ink)] bg-[var(--panel)] p-5 md:flex">
        <Link href="/" className="mb-8 flex items-center gap-3">
          <div className="relative flex h-11 w-11 items-center justify-center border-2 border-[var(--ink)] bg-[var(--hi)] text-[var(--ink)] shadow-[var(--shadow-sm)] transition-transform hover:-rotate-6">
            <Ghost size={28} />
            <span className="absolute -right-1.5 -top-1.5 h-3.5 w-3.5 rounded-full border-2 border-[var(--ink)] bg-[var(--good)]" />
          </div>
          <div>
            <div className="text-lg font-bold leading-none tracking-[0.12em] text-[var(--ink)]">GHOSTKEY</div>
            <div className="mono mt-1 !text-[10px] uppercase text-[var(--ink2)]">identity defense · v2.0</div>
          </div>
        </Link>
        <nav className="flex flex-1 flex-col gap-5 overflow-y-auto">
          {GROUPS.map((g) => (
            <div key={g.label}>
              <div className="eyebrow mb-1.5 px-1 !text-[10px]">// {g.label}</div>
              {g.items.map(({ href, label, icon: Icon }) => (
                <Link
                  key={href}
                  href={href}
                  className={`group relative mb-1 flex items-center gap-3 border-2 px-3 py-2 text-[13px] font-bold uppercase tracking-wide transition-colors ${active(href) ? 'border-[var(--ink)] text-[var(--on-ink)]' : 'border-transparent text-[var(--ink2)] hover:border-[var(--ink)] hover:bg-[var(--hi)] hover:text-[var(--ink)]'}`}
                >
                  {active(href) && (
                    <motion.span layoutId="nav-active" className="absolute -inset-[2px] bg-[var(--ink)] shadow-[3px_3px_0_0_var(--accent)]" transition={{ type: 'spring', stiffness: 500, damping: 38 }} />
                  )}
                  <Icon size={17} className={`relative transition-transform group-hover:translate-x-0.5 ${active(href) ? '' : 'opacity-80 group-hover:opacity-100'}`} />
                  <span className="relative">{label}</span>
                </Link>
              ))}
            </div>
          ))}
        </nav>
        <div className="mt-4"><ThemeToggle /></div>
        <div className="mt-4 -rotate-1 border-2 border-[var(--ink)] bg-[var(--hi)] p-3 text-[12px] font-bold uppercase leading-snug text-[var(--ink)] shadow-[var(--shadow-sm)]">
          Never trust a voice, face, number or account in isolation.
        </div>
      </aside>
      <nav className="sticky top-0 z-40 flex gap-2 overflow-x-auto border-b-2 border-[var(--ink)] bg-[var(--panel)] p-3 md:hidden">
        <ThemeToggle compact />
        {GROUPS.flatMap((g) => g.items).map(({ href, label, icon: Icon }) => (
          <Link key={href} href={href} className={`chip shrink-0 !py-1 ${active(href) ? '!bg-[var(--ink)] !text-[var(--on-ink)]' : ''}`}>
            <Icon size={13} /> {label}
          </Link>
        ))}
      </nav>
    </>
  );
}
