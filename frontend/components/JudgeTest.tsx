'use client';
import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Check, Cpu, Fingerprint, Loader2, Trash2, UserPlus, UserRound, Wand2 } from 'lucide-react';
import { api, postForm } from '@/lib/api';
import AudioPicker from './AudioPicker';
import QuickEnroll from './QuickEnroll';
import { ExplainButton } from './Chat';

type UseCase = 'family' | 'insurance' | 'banking';
const LABEL: Record<string, string> = {
  send_money: 'Send money', emergency_transfer: 'Emergency transfer', chat: 'Just talking', share_otp: 'Asks for an OTP',
  change_contact_details: 'Change contact details', pay_premium: 'Pay premium', submit_high_value_claim: 'High-value claim', change_payout_details: 'Change payout account',
  freeze_payouts: 'Freeze payouts', submit_claim: 'Submit claim', claim_status: 'Claim status', add_nominee: 'Add nominee', balance_enquiry: 'Balance enquiry',
  account_detail_change: 'Change account details', large_transfer: 'Large transfer', freeze_card: 'Freeze card', password_reset: 'Password reset',
  add_payee: 'Add payee', pin_change: 'PIN change',
};

const ROLE: Record<UseCase, string> = { family: 'caller', insurance: 'policyholder', banking: 'customer' };
const exampleName = (uc: UseCase, e: any) => (uc === 'family' ? e?.claimed_caller : uc === 'insurance' ? e?.policyholder : e?.customer);

const Step = ({ n, children }: { n: number; children: React.ReactNode }) => (
  <div className="mb-2 flex items-center gap-2 text-sm font-semibold"><span className="flex h-6 w-6 items-center justify-center rounded-full bg-sky-500/20 text-xs text-blue-600">{n}</span> {children}</div>
);

function contextLine(uc: UseCase, e: any) {
  if (uc === 'family') return `${e.claimed_caller} → ${e.protected_person} · ${LABEL[e.action] ?? e.action}${e.amount ? ` ₹${e.amount.toLocaleString('en-IN')}` : ''}`;
  if (uc === 'insurance') return `${e.policyholder} · ${e.claim_type} · ${LABEL[e.action] ?? e.action}`;
  return `${e.customer} · ${LABEL[e.action] ?? e.action}${e.amount ? ` ₹${e.amount.toLocaleString('en-IN')}` : ''}`;
}

export default function JudgeTest({ useCase, onResult }: { useCase: UseCase; onResult: (r: any) => void }) {
  const [examples, setExamples] = useState<any[]>([]);
  const [ctxId, setCtxId] = useState('');
  const [people, setPeople] = useState<any[]>([]);
  const [personId, setPersonId] = useState('');
  const [newName, setNewName] = useState('');
  const [voiceId, setVoiceId] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [transcript, setTranscript] = useState('');
  const [expected, setExpected] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [credits, setCredits] = useState<any>(null);
  const loadCredits = () => api('provider/status').then((s) => setCredits(s.credits)).catch(() => {});

  useEffect(() => {
    loadCredits();
    api(`examples/${useCase}`).then((d) => {
      setExamples(d.examples);
      setCtxId(d.examples[0]?.id ?? '');
    });
    loadPeople();
  }, [useCase]);
  const loadPeople = () => api('identities').then(setPeople).catch(() => {});
  const voices = people.filter((i) => i.speaker_enrolled);
  const added = people.filter((i) => i.added && i.use_case === useCase);
  const person = people.find((i) => i.id === personId);

  async function addPerson() {
    setError('');
    try {
      const f = new FormData();
      f.append('name', newName.trim());
      f.append('use_case', useCase);
      const p = await postForm('identities', f);
      setNewName('');
      await loadPeople();
      setPersonId(p.id);
      setVoiceId('');
    } catch (e: any) {
      setError(e.message);
    }
  }
  async function removePerson(id: string) {
    setError('');
    try {
      await api(`identities/${id}`, { method: 'DELETE' });
      if (personId === id) setPersonId('');
      if (voiceId === id) setVoiceId('');
      await loadPeople();
    } catch (e: any) {
      setError(e.message);
    }
  }
  function selectPerson(id: string) {
    setPersonId(id);
    const p = people.find((i) => i.id === id);
    setVoiceId(p?.speaker_enrolled ? id : '');
  }
  const ctx = useMemo(() => examples.find((e) => e.id === ctxId), [examples, ctxId]);

  async function run() {
    if (!file || !ctx) return;
    setBusy(true);
    setError('');
    try {
      const f = new FormData();
      f.append('context_id', ctxId);
      f.append('transcript', transcript);
      if (expected) f.append('expected', expected);
      if (voiceId) f.append('speaker_identity_id', voiceId);
      if (personId) f.append('person_identity_id', personId);
      f.append('audio', file);
      onResult(await postForm(`test/${useCase}`, f));
      loadCredits();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <section className="panel glow-border flex flex-col gap-5 lg:col-span-2">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="flex items-center gap-2 text-lg font-semibold"><Wand2 size={18} className="text-blue-600" /> Test it with your own voice</h2>
            <p className="mt-1 text-sm text-[var(--ink2)]">Record yourself or upload any audio (for example an AI clone). It goes to DetectifAI live and through the full multi-agent pipeline.</p>
          </div>
          <ExplainButton topic="voice" />
        </div>

        <div>
          <Step n={1}>Pick the situation your call is part of</Step>
          <select className="input w-full" value={ctxId} onChange={(e) => setCtxId(e.target.value)}>
            {examples.map((e) => <option key={e.id} value={e.id}>{e.id} · {contextLine(useCase, e)}</option>)}
          </select>
          {ctx && (
            <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
              {useCase === 'family' && (<>
                {ctx.carrier_events.map((c: any) => <span key={c.type} className="chip text-pink-700">{c.type.replaceAll('_', ' ')} (simulated)</span>)}
                <span className="chip">independent verification: {ctx.independent_verification ?? 'n/a'}</span>
              </>)}
              {useCase === 'insurance' && (<>
                <span className="chip">{ctx.documents.length}/{ctx.required_documents.length} documents</span>
                {ctx.anomaly && <span className="chip text-pink-700">{ctx.anomaly.replace('_', ' ')}</span>}
                <span className="chip">{ctx.auth ? 'code + device approval done' : 'no authentication yet'}</span>
              </>)}
              {useCase === 'banking' && (<>
                <span className="chip">role: {ctx.role}</span>
                <span className="chip">{ctx.auth === 'full' ? 'code + device approval done' : ctx.auth === 'challenge_only' ? 'code only' : ctx.auth === 'replay' ? 'replayed code' : 'no authentication yet'}</span>
              </>)}
              <span className="chip text-amber-700">context is synthetic</span>
            </div>
          )}
        </div>

        <div>
          <Step n={2}>Who is the {ROLE[useCase]}? Add yourself or anyone</Step>
          <div className="flex flex-wrap gap-2">
            <button onClick={() => selectPerson('')} className={`chip !py-1.5 ${!personId ? 'border-sky-400 bg-sky-500/10 text-blue-700' : ''}`}>
              {!personId ? <Check size={12} /> : <UserRound size={12} />} As in the example: {exampleName(useCase, ctx) ?? '—'}
            </button>
            {added.map((p) => (
              <span key={p.id} className={`chip !py-1.5 ${personId === p.id ? 'border-sky-400 bg-sky-500/10 text-blue-700' : ''}`}>
                <button className="flex items-center gap-1" onClick={() => selectPerson(p.id)}>
                  {personId === p.id ? <Check size={12} /> : <UserRound size={12} />} {p.name} {p.speaker_enrolled && <Fingerprint size={12} className="text-violet-600" />}
                </button>
                <button title="Delete this person and their voiceprint" className="ml-1 text-[var(--ink2)] hover:text-red-600" onClick={() => removePerson(p.id)}><Trash2 size={11} /></button>
              </span>
            ))}
          </div>
          <div className="mt-2 flex gap-2">
            <input className="input min-w-0 flex-1" placeholder={`Name of the ${ROLE[useCase]} (e.g. your name)`} value={newName} onChange={(e) => setNewName(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && newName.trim() && addPerson()} />
            <button className="btn" disabled={!newName.trim()} onClick={addPerson}><UserPlus size={15} /> Add to database</button>
          </div>
          {person && (
            <div className="fade-in mt-3 rounded-none border border-violet-500/30 bg-violet-500/[0.06] p-3">
              <div className="mb-2 flex items-center justify-between gap-2 text-sm">
                <span className="flex items-center gap-2 font-medium"><Fingerprint size={15} className="text-violet-600" /> {person.name}</span>
                <span className={`chip ${person.speaker_enrolled ? 'text-teal-700' : 'text-[var(--ink2)]'}`}>{person.speaker_enrolled ? 'voiceprint enrolled' : 'no voiceprint yet'}</span>
              </div>
              {person.speaker_enrolled ? (
                <p className="text-[12.5px] text-[var(--ink2)]">Saved. The test below is checked against this voiceprint (speaker match) and for AI artefacts (deepfake). Re-enroll any time from Speaker enrollment.</p>
              ) : (
                <>
                  <p className="mb-2 text-[12.5px] text-[var(--ink2)]">Optional: enroll {person.name.split(' ')[0]}&apos;s real voice (about 10 seconds) so the test can compare against it — then try a clone of the same voice.</p>
                  <QuickEnroll key={person.id} identityId={person.id} name={person.name} compact onEnrolled={async () => { await loadPeople(); setVoiceId(person.id); }} />
                </>
              )}
            </div>
          )}
        </div>

        <div>
          <Step n={3}>The voice to test</Step>
          <AudioPicker file={file} onFile={setFile} autoPickNew />
          <input className="input mt-3 w-full" placeholder="Optional: what was said (used to spot pressure words like 'urgent', 'OTP')" value={transcript} onChange={(e) => setTranscript(e.target.value)} />
        </div>

        <div>
          <Step n={4}>Check against a voiceprint (optional)</Step>
          <select className="input w-full" value={voiceId} onChange={(e) => setVoiceId(e.target.value)}>
            <option value="">Deepfake check only (1 check)</option>
            {voices.map((v) => <option key={v.id} value={v.id}>Compare with {v.name}'s voiceprint (speaker + deepfake, 2 checks)</option>)}
          </select>
          <p className="mt-1 text-[11.5px] text-[var(--ink2)]">To test a clone of yourself: add yourself in step 2, enroll about 10 s of your real voice, then upload the clone in step 3. (Also on <Link href="/speakers" className="text-blue-600 hover:underline">Speaker enrollment</Link>.)</p>
        </div>

        <div>
          <Step n={5}>What is this audio really? (optional — the test report is judged against it)</Step>
          <div className="tabs">
            {[['', 'Not specified'], ['same_person', 'The enrolled person'], ['different_person', 'Someone else'], ['ai_voice', 'AI clone / TTS'], ['real_human', 'A real human']].map(([v, l]) => (
              <button key={v} className={`tab !py-1 ${expected === v ? 'tab-active' : ''}`} aria-pressed={expected === v} onClick={() => setExpected(v)}>{l}</button>
            ))}
          </div>
        </div>

        <button className="btn btn-primary w-fit !px-5 !py-2.5" disabled={!file || !ctx || busy} onClick={run}>
          {busy ? <Loader2 size={16} className="animate-spin" /> : <Cpu size={16} />} {busy ? 'Analysing with DetectifAI…' : 'Run live test'}
        </button>
        {credits && !credits.unlimited && credits.available !== undefined && (
          <p className={`text-xs ${credits.available < 200 ? 'text-amber-700' : 'text-[var(--ink2)]'}`}>
            DetectifAI credits left: {credits.available} (≈ {Math.floor(credits.available / (credits.price_per_operation || 50))} checks). {credits.available < 200 && 'Running low — ask the DetectifAI team for more.'}
          </p>
        )}
        {error && <p className="text-sm text-red-600">{error}</p>}
      </section>

      <aside className="panel flex flex-col gap-3 text-sm">
        <h3 className="font-semibold">What to try</h3>
        {[
          ['Your real voice', 'Expect "no synthetic indicators". The action still needs the checks this situation requires — a genuine voice alone never authorizes.', '#0d9488'],
          ['An AI clone / TTS voice', 'Expect "synthetic indicators". Money or account changes are held or escalated.', '#e11d48'],
          ['Add yourself + a clone of you', 'Step 2: add your name and enroll about 10 s of your voice. Step 3: upload the clone. Expect speaker match + synthetic: the critic flags a possible clone.', '#7c3aed'],
          ['Audio played through a speaker', 'Re-recorded audio is harder to judge; DetectifAI\'s docs say it is less reliable. Uploading the file is a cleaner test.', '#d97706'],
        ].map(([t, d, c]) => (
          <div key={t} className="rounded-none border-2 border-[var(--ink)] bg-[var(--panel2)] p-3">
            <div className="flex items-center gap-2 font-medium" style={{ color: c }}><Fingerprint size={14} /> {t}</div>
            <div className="mt-1 text-[12.5px] text-[var(--ink2)]">{d}</div>
          </div>
        ))}
        <p className="text-[11.5px] text-[var(--ink2)]">Your audio is processed in memory and not stored. People you add are saved in the GhostKey database (name + DetectifAI voiceprint id) until you delete them. Each run and each enrollment uses DetectifAI credits.</p>
      </aside>
    </div>
  );
}
