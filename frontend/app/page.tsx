'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { motion } from 'motion/react';
import {
  Activity, AlertTriangle, ArrowRight, AudioWaveform, Building2, CheckCircle2, ClipboardCheck, Fingerprint, FlaskConical, GitBranch, GraduationCap, Hourglass, Loader2,
  Play, Radio, Scale, ShieldAlert, ShieldCheck, ShieldX, Smartphone, Swords, Umbrella, Zap,
} from 'lucide-react';
import { api, STATUS } from '@/lib/api';
import { PAGE_ICON } from '@/lib/icons';
import { Skeleton, StatusPill } from '@/components/viz';
import { Counter, SectionTitle } from '@/components/ui';
import { ExplainButton } from '@/components/Chat';

const USE_CASES = [
  { id: 'family', href: '/family', title: 'Family & SIM', icon: PAGE_ICON.family, color: '#ff7ac2', text: 'Relatives asking for money from a reassigned or hijacked number.' },
  { id: 'exam', href: '/exam', title: 'Exam identity', icon: PAGE_ICON.exam, color: '#5b8cff', text: 'A substitute sitting an online exam for a registered student.' },
  { id: 'insurance', href: '/insurance', title: 'Insurance claims', icon: PAGE_ICON.insurance, color: '#a98bff', text: 'Impersonators submitting claims or redirecting payouts.' },
  { id: 'banking', href: '/banking', title: 'Banking', icon: PAGE_ICON.banking, color: '#35d6c4', text: 'Cloned voices asking for PIN, recovery or payee changes.' },
];
const OUTCOMES = [
  { id: 'VERIFIED_AND_AUTHORIZED', label: 'Verified', icon: ShieldCheck, color: 'var(--good)' },
  { id: 'HOLD_FOR_VERIFICATION', label: 'Held', icon: Hourglass, color: 'var(--warn)' },
  { id: 'ESCALATED_FOR_REVIEW', label: 'Escalated', icon: ShieldAlert, color: 'var(--warn)' },
  { id: 'DENIED', label: 'Denied', icon: ShieldX, color: 'var(--bad)' },
];

const TEAM_COLORS = ['#ffe14d', '#c9f3e2', '#e2e2ff', '#ffd6d0', '#ffe7b8', '#0b0b0b'];
const reveal = { initial: { opacity: 0, y: 24 }, whileInView: { opacity: 1, y: 0 }, viewport: { once: true, margin: '-40px' } } as const;

/** The pipeline as a "team": the six roles every request passes through (same names as before, no data). */
function Workflow() {
  const nodes = [['Voice', Radio], ['Speaker', Fingerprint], ['Context', Scale], ['Critic', Swords], ['Evidence', GitBranch], ['Policy', ShieldCheck]] as const;
  return (
    <section aria-label="Agent workflow: voice, speaker, context, critic, evidence, policy">
      <SectionTitle icon={Swords}>How every request is decided</SectionTitle>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {nodes.map(([label, Icon], i) => (
          <motion.div key={label} {...reveal} transition={{ delay: i * 0.07, type: 'spring', stiffness: 260, damping: 20 }}
            whileHover={{ y: -6, rotate: i % 2 ? 1.5 : -1.5 }}
            className="group relative border-2 border-[var(--ink)] bg-[var(--panel)] shadow-[var(--shadow)]">
            <div className="grid aspect-square place-items-center border-b-2 border-[var(--ink)]" style={{ background: TEAM_COLORS[i], color: i === 5 ? '#fff' : '#0b0b0b' }}>
              <Icon size={44} strokeWidth={1.6} className="transition-transform duration-300 group-hover:scale-110" />
            </div>
            <div className="flex items-center justify-between px-3 py-2">
              <span className="text-[15px] font-bold uppercase">{label}</span>
              <span className="mono !text-[11px] text-[var(--ink3)]">{String(i + 1).padStart(2, '0')}</span>
            </div>
            {i < nodes.length - 1 && <ArrowRight size={18} className="absolute -right-[19px] top-1/3 z-10 hidden bg-[var(--bg)] lg:block" />}
          </motion.div>
        ))}
      </div>
    </section>
  );
}

function Marquee({ items }: { items: string[] }) {
  return (
    <div className="marquee -mx-4 md:-mx-8" aria-hidden="true">
      <div className="marquee-track">
        {[0, 1].map((k) => (
          <div key={k} className="flex">
            {items.map((t, i) => <span key={i} className="marquee-item">{t} <span className="text-[var(--hi)]">✦</span></span>)}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [status, setStatus] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  const [reports, setReports] = useState<any>(null);
  const [error, setError] = useState('');

  const refresh = () => {
    api('stats').then(setStats).catch(() => {});
    api('reports/stats').then(setReports).catch(() => {});
  };
  useEffect(() => {
    api('provider/status').then(setStatus).catch((e) => setError(e.message));
    refresh();
  }, []);

  const credits = status?.credits;
  const alerts: [string, string][] = [];
  if (error) alerts.push(['bad', `Status check failed: ${error}`]);
  if (status && !status.health?.reachable) alerts.push(['bad', `DetectifAI unreachable: ${status.health?.error ?? 'no response'}`]);
  if (status && !status.key_configured) alerts.push(['bad', 'DetectifAI key missing — set DETECTIF_API_KEY in the server environment (backend/.env locally, Variables on Railway)']);
  if (credits?.error) alerts.push(['bad', `Credits check failed: ${credits.error}`]);
  if (!credits?.unlimited && typeof credits?.available === 'number' && credits.available < 300) alerts.push(['warn', `Only ${credits.available} DetectifAI credits left (about ${Math.floor(credits.available / (credits.price_per_operation || 50))} checks).`]);
  if (status && !status.face_model?.available) alerts.push(['warn', 'Face model files missing — exam checks unavailable.']);
  if (reports?.by_status?.ERROR) alerts.push(['warn', `${reports.by_status.ERROR} test(s) ended in ERROR — see Test reports.`]);
  return (
    <div className="flex flex-col gap-14">
      <section className="relative pt-2">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
          <span className="chip st-run mb-5 !px-3 !py-1"><Zap size={12} /> Multi-agent identity defense</span>
          <h1 className="max-w-6xl text-[44px] leading-[0.92] sm:text-6xl md:text-7xl xl:text-[104px]">
            A convincing voice or face{' '}
            <motion.span initial={{ backgroundSize: '0% 100%' }} animate={{ backgroundSize: '100% 100%' }} transition={{ delay: 0.35, duration: 0.6, ease: 'easeOut' }}
              className="bg-no-repeat px-1" style={{ color: '#0b0b0b', backgroundImage: 'linear-gradient(var(--hi), var(--hi))', boxDecorationBreak: 'clone', WebkitBoxDecorationBreak: 'clone' }}>
              is never enough.
            </motion.span>
          </h1>
        </motion.div>
        <div className="mt-6 grid items-end gap-6 lg:grid-cols-[1.3fr_1fr]">
          <p className="max-w-2xl border-l-4 border-[var(--ink)] pl-4 text-[17px] leading-relaxed text-[var(--ink2)]">
            Specialist agents gather evidence, a critic challenges them, and a fixed rulebook — not an AI — decides. Every test leaves a report.
          </p>
          <div className="flex flex-wrap items-center gap-2 lg:justify-end">
            {!status ? <><Skeleton className="h-6 w-28" /><Skeleton className="h-6 w-24" /></> : (
              <>
                <span className={`chip ${status.health?.reachable ? 'st-pass' : 'st-fail'}`}><span className={`h-2 w-2 rounded-full ${status.health?.reachable ? 'bg-[var(--good)]' : 'bg-[var(--bad)]'}`} /> DetectifAI {status.health?.reachable ? 'online' : 'offline'}</span>
                <span className={`chip ${status.key_configured ? 'st-pass' : 'st-fail'}`}>key {status.key_configured ? 'on backend' : 'missing'}</span>
                <span className="chip">{credits?.unlimited ? 'unlimited credits' : credits?.available !== undefined ? `${credits.available} credits` : 'credits n/a'}</span>
                <span className={`chip ${status.face_model?.available ? 'st-pass' : 'st-hold'}`}>face model {status.face_model?.available ? 'loaded' : 'missing'}</span>
                <ExplainButton topic="status" />
              </>
            )}
          </div>
        </div>
      </section>

      <Marquee items={[...USE_CASES.map((u) => u.title), ...OUTCOMES.map((o) => o.label), ...USE_CASES.map((u) => u.title), ...OUTCOMES.map((o) => o.label)]} />

      {alerts.length > 0 && (
        <section className="flex flex-col gap-2" aria-live="polite">
          {alerts.map(([tone, msg]) => (
            <div key={msg} role="alert" className={`flex items-center gap-2 rounded-none border px-3.5 py-2.5 text-sm ${tone === 'bad' ? 'st-fail' : 'st-hold'}`}><AlertTriangle size={15} /> {msg}</div>
          ))}
        </section>
      )}

      <section>
        <SectionTitle icon={PAGE_ICON.reports} right={<Link href="/reports" className="text-xs font-semibold text-[var(--accent)] hover:underline">All test reports →</Link>}>Test outcomes</SectionTitle>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
          <Link href="/reports" className="panel panel-hover !bg-[var(--ink)] !p-4 text-[var(--on-ink)]">
            <div className="mono flex items-center gap-2 !text-[11px] uppercase text-[var(--on-ink)] opacity-80"><Activity size={14} /> Tests run</div>
            <div className="mt-1 text-5xl font-bold tabular-nums">{reports ? <Counter value={reports.total} /> : <Skeleton className="h-8 w-14" />}</div>
          </Link>
          {(['PASS', 'FAIL', 'HOLD', 'ERROR', 'SKIPPED'] as const).map((k) => (
            <Link key={k} href="/reports" className="panel panel-hover !p-4">
              <div className="text-xs text-[var(--ink2)]"><StatusPill status={k} /></div>
              <div className="mt-1 text-5xl font-bold tabular-nums" style={{ color: STATUS[k].color }}>{reports ? <Counter value={reports.by_status?.[k] ?? 0} /> : <Skeleton className="h-8 w-10" />}</div>
              <div className="mt-2 h-2 overflow-hidden border-[1.5px] border-[var(--ink)] bg-[var(--panel)]">
                <motion.div className="h-full rounded-none" style={{ background: STATUS[k].color }} initial={{ width: 0 }} animate={{ width: `${reports?.total ? ((reports.by_status?.[k] ?? 0) / reports.total) * 100 : 0}%` }} transition={{ duration: 0.8 }} />
              </div>
            </Link>
          ))}
        </div>
      </section>

      <section>
        <SectionTitle icon={Zap}>Quick actions</SectionTitle>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5 stagger">
          {[
            { href: '/speakers', title: 'Voice verification', text: 'Enroll a speaker, verify a new recording.', icon: PAGE_ICON.speakers },
            { href: '/voice', title: 'Deepfake check', text: 'Is this audio AI-generated?', icon: PAGE_ICON.voice },
            { href: '/exam', title: 'Exam verification', text: 'Face match with a consented reference.', icon: PAGE_ICON.exam },
            { href: '/insurance', title: 'Insurance claim', text: 'Claim plus caller verification.', icon: PAGE_ICON.insurance },
            { href: '/scenarios', title: 'Scenario testing', text: '17 scripted scenarios with expected outcomes.', icon: FlaskConical },
          ].map((a) => (
            <Link key={a.title} href={a.href} className="panel panel-hover group flex flex-col gap-2 !p-4">
              <div className="flex items-center justify-between">
                <span className="grid size-10 place-items-center border-2 border-[var(--ink)] bg-[var(--hi)] transition-transform group-hover:-rotate-6"><a.icon size={19} /></span>
                <ArrowRight size={18} className="transition group-hover:translate-x-1" />
              </div>
              <div className="text-[17px] font-bold uppercase leading-tight">{a.title}</div>
              <p className="text-[13px] text-[var(--ink2)]">{a.text}</p>
            </Link>
          ))}
        </div>
      </section>

      <section>
        <SectionTitle icon={ShieldCheck} explain="overview">Protected use cases</SectionTitle>
        <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
          {USE_CASES.map((u, i) => (
            <motion.div key={u.id} {...reveal} transition={{ delay: i * 0.08, type: 'spring', stiffness: 240, damping: 22 }} whileHover={{ y: -6, rotate: i % 2 ? 1 : -1 }}>
              <Link href={u.href} className="group flex h-full flex-col border-2 border-[var(--ink)] bg-[var(--panel)] shadow-[var(--shadow)] transition-shadow hover:shadow-[var(--shadow-lg)]">
                <div className="relative flex h-40 items-end justify-between overflow-hidden border-b-2 border-[var(--ink)] p-4" style={{ background: u.color }}>
                  <span className="pointer-events-none absolute -right-2 -top-6 select-none text-[120px] font-bold leading-none text-white/25">{String(i + 1).padStart(2, '0')}</span>
                  <span className="grid size-14 place-items-center border-2 border-[var(--ink)] bg-[var(--panel)] text-[var(--ink)] shadow-[var(--shadow-sm)] transition-transform duration-300 group-hover:-rotate-6 group-hover:scale-105"><u.icon size={28} /></span>
                  <span className="mono border-2 border-[var(--ink)] bg-[var(--panel)] px-2 py-0.5 !text-[11px] font-bold uppercase">{stats?.by_use_case?.[u.id] ?? 0} investigations</span>
                </div>
                <div className="flex flex-1 flex-col gap-2 p-4">
                  <span className="text-2xl font-bold uppercase leading-none">{u.title}</span>
                  <span className="text-[13.5px] text-[var(--ink2)]">{u.text}</span>
                  <ArrowRight size={20} className="mt-auto self-end transition-transform group-hover:translate-x-1" />
                </div>
              </Link>
            </motion.div>
          ))}
        </div>
      </section>

      <Workflow />

    </div>
  );
}
