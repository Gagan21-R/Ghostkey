'use client';
import { useEffect, useState } from 'react';
import { AudioLines, Bot, Cpu, GalleryHorizontal, LayoutGrid, Loader2, Play, ScanFace, User, Users } from 'lucide-react';
import { api } from '@/lib/api';
import { ExplainButton } from './Chat';
import MomentumRail, { RailDetails, RailLayer } from './MomentumRail';

type UseCase = 'exam' | 'family' | 'insurance' | 'banking';
const ACTION_LABEL: Record<string, string> = {
  send_money: 'Send money', emergency_transfer: 'Emergency transfer', chat: 'Just talking', share_otp: 'Asks for an OTP',
  change_contact_details: 'Change contact details', pay_premium: 'Pay premium', submit_high_value_claim: 'High-value claim',
  change_payout_details: 'Change payout account', freeze_payouts: 'Freeze payouts', submit_claim: 'Submit claim', claim_status: 'Claim status', add_nominee: 'Add nominee',
  balance_enquiry: 'Balance enquiry', account_detail_change: 'Change account details', large_transfer: 'Large transfer', freeze_card: 'Freeze card',
  password_reset: 'Password reset', add_payee: 'Add payee', pin_change: 'PIN change',
};
const truthTone = (t: string) => (t === 'same person' ? '#0d9488' : t === 'different person' ? '#e11d48' : '#d97706');

const personOf = (uc: UseCase, e: any) => (uc === 'exam' ? e.student : uc === 'family' ? e.claimed_caller : uc === 'banking' ? e.customer : e.policyholder);
const subOf = (uc: UseCase, e: any) => (uc === 'exam' ? e.scenario : uc === 'family' ? `calls ${e.protected_person}` : uc === 'banking' ? 'calls the bank' : `${e.claim_type} · ${e.claim_id}`);
const initials = (name: string) => name.replace(/\(.*?\)/g, '').trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join('').toUpperCase();

function hash(s: string) {
  let h = 2166136261;
  for (const c of s) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
  return h >>> 0;
}

/** Deterministic waveform art per example; bars breathe while the card is centered. */
function Waveform({ seed, color, active }: { seed: string; color: string; active: boolean }) {
  let h = hash(seed);
  const bars = Array.from({ length: 34 }, (_, i) => {
    h = Math.imul(h ^ (h >>> 13), 1274126177) >>> 0;
    const env = Math.sin((i / 33) * Math.PI) * 0.75 + 0.25;
    return 10 + ((h % 1000) / 1000) * 70 * env;
  });
  return (
    <svg viewBox="0 0 208 100" preserveAspectRatio="none" className="h-full w-full" aria-hidden="true">
      {bars.map((b, i) => (
        <rect
          key={i}
          x={8 + i * 5.7}
          y={50 - b / 2}
          width={3.2}
          height={b}
          rx={1.6}
          fill={color}
          opacity={0.35 + (i % 5) * 0.12}
          className={active ? 'gk-bar' : ''}
          style={{ animationDelay: `${(i % 9) * 0.09}s`, transformOrigin: `0 50px` }}
        />
      ))}
    </svg>
  );
}

function ExampleCard({ e, useCase, busy, run, active, flat }: { e: any; useCase: UseCase; busy: string; run: (id: string, live: boolean) => void; active: boolean; flat?: boolean }) {
  const ai = e.voice_truth === 'ai_synthetic';
  const tone = useCase === 'exam' ? truthTone(e.ground_truth) : ai ? '#e11d48' : '#0d9488';
  const name = personOf(useCase, e);
  const Details: React.ElementType = flat ? 'div' : RailDetails;

  return (
    <article
      className="group relative flex h-full flex-col overflow-hidden border-2 border-[var(--ink)] bg-[var(--panel)] transition-[box-shadow,transform] duration-200"
      style={active ? { boxShadow: `7px 7px 0 0 ${tone}, 7px 7px 0 2px var(--ink)`, transform: 'translate(-3px,-3px)' } : { boxShadow: 'var(--shadow)' }}
    >
      {/* visual */}
      <div className="relative aspect-[4/3] overflow-hidden border-b-2 border-[var(--ink)]" style={{ background: useCase === 'exam' ? '#0f172a' : `radial-gradient(120% 90% at 20% 10%, ${tone}22, transparent 60%), linear-gradient(160deg, var(--panel), var(--panel2))` }}>
        {useCase === 'exam' ? (
          e.reference_url ? (
            <RailLayer depth={7}>
              {/* biome-ignore lint/performance/noImgElement: static example media */}
              <img src={e.reference_url} alt={`${name} — enrolled reference`} draggable={false} className="h-full w-full object-cover" />
            </RailLayer>
          ) : (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 text-xs text-[var(--ink2)]"><ScanFace size={34} /> no reference enrolled</div>
          )
        ) : (
          <>
            <RailLayer depth={10}><Waveform seed={e.id} color={tone} active={active || !!flat} /></RailLayer>
            <div className="absolute left-4 top-1/2 grid size-14 -translate-y-1/2 place-items-center rounded-full border-2 bg-[var(--panel)] text-lg font-semibold shadow-[var(--shadow-sm)]" style={{ borderColor: `${tone}55`, color: tone }}>
              {initials(name)}
            </div>
          </>
        )}
        <div className={`pointer-events-none absolute inset-x-0 bottom-0 h-2/3 bg-gradient-to-t ${useCase === 'exam' ? 'from-black/80 via-black/35' : 'from-[var(--panel)] via-[color-mix(in_srgb,var(--panel)_80%,transparent)]'} to-transparent`} />
        <span className="absolute left-3 top-3 rounded-none bg-black/60 px-1.5 py-0.5 font-mono text-[11px] text-white backdrop-blur">{e.id}</span>
        <span className="absolute right-3 top-3 flex max-w-[65%] items-center gap-1 truncate rounded-full px-2 py-0.5 text-[11px] font-medium backdrop-blur" style={{ background: 'var(--panel)', color: tone, border: `1px solid ${tone}66` }}>
          {useCase === 'exam' ? <><Users size={11} className="shrink-0" /> <span className="truncate">{e.ground_truth}</span></> : ai ? <><Bot size={11} /> AI voice</> : <><User size={11} /> real human</>}
        </span>
        {useCase === 'exam' && (
          <div className="absolute bottom-14 right-3 flex gap-1">
            {e.frame_urls.slice(0, 3).map((u: string, i: number) => (
              // biome-ignore lint/performance/noImgElement: static example media
              <img key={i} src={u} alt={`observed frame ${i + 1}`} draggable={false} className="h-12 w-9 rounded-none border border-white/25 object-cover shadow-[var(--shadow)]" />
            ))}
          </div>
        )}
        <div className="absolute inset-x-3 bottom-3">
          <div className={`truncate font-semibold leading-tight ${useCase === 'exam' ? 'text-white' : 'text-[var(--ink)]'}`}>{name}</div>
          <div className={`truncate text-[12px] ${useCase === 'exam' ? 'text-white/75' : 'text-[var(--ink2)]'}`}>{subOf(useCase, e)}</div>
        </div>
      </div>

      {/* body */}
      <div className="flex flex-1 flex-col gap-2.5 p-3.5">
        {useCase !== 'exam' && <audio controls preload="none" src={e.audio_url} className="h-9 w-full" />}
        <Details className="flex flex-col gap-2">
          {useCase !== 'exam' && <p className="line-clamp-2 text-[12.5px] italic text-[var(--ink)]/80">“{e.transcript}”</p>}
          <div className="flex flex-wrap gap-1.5 text-[11px]">
            {useCase === 'exam' && <span className="chip">{e.frame_urls.length} frames</span>}
            {useCase !== 'exam' && <span className="chip text-amber-800">{ACTION_LABEL[e.action] ?? e.action}{e.amount ? ` ₹${e.amount.toLocaleString('en-IN')}` : ''}</span>}
            {useCase === 'family' && (
              <>
                {e.carrier_events.map((c: any) => <span key={c.type} className="chip text-pink-700">{c.type.replaceAll('_', ' ')} (sim)</span>)}
                {e.account_events.map((c: any) => <span key={c.type} className="chip text-pink-700">{c.type.replaceAll('_', ' ')}</span>)}
                <span className="chip">verification: {e.independent_verification ?? 'n/a'}</span>
              </>
            )}
            {useCase === 'banking' && (
              <>
                <span className="chip">role: {e.role}</span>
                <span className="chip">{e.auth === 'full' ? 'code + approval done' : e.auth === 'challenge_only' ? 'code only' : e.auth === 'replay' ? 'replayed code' : 'no authentication'}</span>
              </>
            )}
            {useCase === 'insurance' && (
              <>
                <span className="chip">{e.documents.length}/{e.required_documents.length} docs</span>
                {e.anomaly && <span className="chip text-pink-700">{e.anomaly.replace('_', ' ')}</span>}
                <span className="chip">{e.auth ? 'code + approval done' : 'no authentication'}</span>
              </>
            )}
          </div>
          <div className="line-clamp-2 text-[11px] text-[var(--ink2)]">{useCase === 'exam' ? e.notes : e.voice_source}</div>
        </Details>

        <div className="mt-auto flex flex-wrap gap-2 pt-1">
          <button className="btn !px-3 !py-1.5 text-[13px]" disabled={!!busy} onClick={() => run(e.id, false)}>
            {busy === e.id ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} {useCase === 'exam' ? 'Run face check' : 'Run (free)'}
          </button>
          {useCase !== 'exam' && (
            <button className="btn btn-primary !px-3 !py-1.5 text-[13px]" disabled={!!busy} onClick={() => run(e.id, true)} title="Sends this audio to DetectifAI (1 check, 50 credits)">
              {busy === e.id + '-live' ? <Loader2 size={14} className="animate-spin" /> : <Cpu size={14} />} DetectifAI
            </button>
          )}
        </div>
      </div>
    </article>
  );
}

export default function ExamplesGallery({ useCase, onResult }: { useCase: UseCase; onResult: (r: any) => void }) {
  const [data, setData] = useState<any>(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<'all' | 'human' | 'ai'>('all');
  const [view, setView] = useState<'rail' | 'grid'>('rail');
  useEffect(() => { api(`examples/${useCase}`).then(setData).catch((e) => setError(e.message)); }, [useCase]);

  async function run(id: string, live: boolean) {
    setBusy(id + (live ? '-live' : ''));
    setError('');
    try {
      onResult(await api(`examples/${useCase}/${id}/run?live=${live}`, { method: 'POST' }));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy('');
    }
  }

  if (error && !data) return <p className="text-red-600">{error}</p>;
  if (!data) return <div className="flex items-center gap-2 text-[var(--ink2)]"><Loader2 className="animate-spin" size={16} /> Loading examples…</div>;
  const items = data.examples.filter((e: any) => filter === 'all' || (filter === 'human' ? e.voice_truth !== 'ai_synthetic' : e.voice_truth === 'ai_synthetic'));
  const humans = data.examples.filter((e: any) => e.voice_truth !== 'ai_synthetic').length;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-3xl text-sm text-[var(--ink2)]">{data.note ?? data.source} {data.grouping ? `· ${data.grouping}` : ''}</p>
        <div className="flex items-center gap-2">
          {useCase !== 'exam' && (
            <div className="tabs">
              {(['all', 'human', 'ai'] as const).map((f) => (
                <button key={f} className={`tab !py-1 ${filter === f ? 'tab-active' : ''}`} onClick={() => setFilter(f)}>{f === 'all' ? 'All' : f === 'human' ? 'Real humans' : 'AI voices'}</button>
              ))}
            </div>
          )}
          <div className="tabs">
            <button className={`tab !px-2 !py-1 ${view === 'rail' ? 'tab-active' : ''}`} title="Rail view" onClick={() => setView('rail')}><GalleryHorizontal size={15} /></button>
            <button className={`tab !px-2 !py-1 ${view === 'grid' ? 'tab-active' : ''}`} title="Grid view" onClick={() => setView('grid')}><LayoutGrid size={15} /></button>
          </div>
          <ExplainButton topic="examples" />
        </div>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}

      {view === 'rail' ? (
        <MomentumRail
          key={filter}
          items={items}
          getKey={(e: any) => e.id}
          eyebrow={useCase === 'exam' ? `${items.length} students · real photos, real face model` : `${humans} real callers · ${data.examples.length - humans} labelled AI voices`}
          title={useCase === 'exam' ? 'Face cards — drag, flick or use ← →' : 'Voice cards — drag, flick or use ← →'}
          renderCard={(e: any, { active }) => <ExampleCard e={e} useCase={useCase} busy={busy} run={run} active={active} />}
        />
      ) : (
        <div className="stagger grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {items.map((e: any) => <ExampleCard key={e.id} e={e} useCase={useCase} busy={busy} run={run} active={false} flat />)}
        </div>
      )}
      {useCase !== 'exam' && <div className="flex items-center gap-1 text-[11px] text-[var(--ink2)]"><AudioLines size={11} /> "Run" skips the voice check (shown as missing evidence); the blue DetectifAI button spends 1 check.</div>}
    </div>
  );
}
