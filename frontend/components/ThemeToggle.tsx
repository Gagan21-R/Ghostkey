'use client';
import { useEffect, useState } from 'react';
import { motion } from 'motion/react';
import { Moon, Sun } from 'lucide-react';

export const THEME_KEY = 'ghostkey-theme';

/** Light / dark switch. The choice is remembered in this browser (localStorage, best effort). */
export default function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  useEffect(() => {
    setTheme(document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light');
  }, []);
  function toggle() {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem(THEME_KEY, next); } catch {}
  }
  const dark = theme === 'dark';
  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={dark}
      aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
      title={dark ? 'Light mode' : 'Dark mode'}
      className={`group flex items-center gap-2 border-2 border-[var(--ink)] bg-[var(--panel)] font-bold uppercase shadow-[var(--shadow-sm)] transition-transform hover:-translate-x-px hover:-translate-y-px active:translate-x-0.5 active:translate-y-0.5 ${compact ? 'px-2 py-1 text-[11px]' : 'w-full justify-between px-3 py-2 text-[12px]'}`}
    >
      {!compact && <span>{dark ? 'Dark mode' : 'Light mode'}</span>}
      <span className="relative flex h-6 w-11 items-center border-2 border-[var(--ink)] bg-[var(--panel2)]">
        <motion.span layout transition={{ type: 'spring', stiffness: 600, damping: 32 }}
          className={`absolute grid size-5 place-items-center border-l-2 border-r-2 border-[var(--ink)] bg-[var(--hi)] ${dark ? 'right-0 border-r-0' : 'left-0 border-l-0'}`}>
          {dark ? <Moon size={12} /> : <Sun size={12} />}
        </motion.span>
      </span>
    </button>
  );
}
