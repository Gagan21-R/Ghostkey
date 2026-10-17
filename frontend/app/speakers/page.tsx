'use client';
import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Fingerprint, Play, Trash2, UserPlus } from 'lucide-react';
import { PAGE_ICON } from '@/lib/icons';
import { api, postForm } from '@/lib/api';
import AudioPicker from '@/components/AudioPicker';
import QuickEnroll from '@/components/QuickEnroll';
import RegionHero from '@/components/RegionHero';
import { ErrorBanner, Progress, ResultHero, SpeakerCompare, VoiceMeter } from '@/components/viz';

const USE_CASES = [['banking', 'Banking'], ['family', 'Family & SIM'], ['insurance', 'Insurance'], ['exam', 'Exam']];
const STAGES = ['Validating audio', 'Submitting verification request', 'Processing provider response', 'Saving test report'];
const HERO: Record<string, string> = { MATCH: 'VERIFIED_AND_AUTHORIZED', NO_MATCH: 'DENIED', INCONCLUSIVE: 'HOLD_FOR_VERIFICATION', NOT_VERIFIED: 'HOLD_FOR_VERIFICATION' };

export default function SpeakersPage() {
  const [ids, setIds] = useState<any[]>([]);
  const [identityId, setIdentityId] = useState('');
  const [newName, setNewName] = useState('');
  const [newUc, setNewUc] = useState('banking');
  const [showEnroll, setShowEnroll] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [expected, setExpected] = useState('');
  const [stage, setStage] = useState(-1);
  const [res, setRes] = useState<any>(null);
  const [error, setError] = useState<{ msg: string; reportId?: string } | null>(null);
  const attempt = useRef('');

  const load = () => api('identities').then((l) => { setIds(l); setIdentityId((x) => x || l.find((i: any) => i.speaker_enrolled)?.id || l[0]?.id || ''); });
  useEffect(() => { load(); }, []);
  const ident = ids.find((i) => i.id === identityId);
  // a new person, file or expectation is a new attempt: never leave the previous result on screen
  useEffect(() => { setRes(null); setError(null); }, [identityId, file, expected]);
  useEffect(() => { setShowEnroll(!!ident && !ident.speaker_enrolled); }, [identityId, ident?.speaker_enrolled]); // eslint-disable-line react-hooks/exhaustive-deps

  async function create() {
    try {
      const f = new FormData();
      f.append('name', newName.trim());
      f.append('use_case', newUc);
      const i = await postForm('identities', f);
      setNewName('');
      await load();
      setIdentityId(i.id);
    } catch (e: any) { setError({ msg: e.message }); }
  }
  async function remove() {
    try {
      await api(`identities/${identityId}`, { method: 'DELETE' });
      setIdentityId('');
      await load();
    } catch (e: any) { setError({ msg: e.message }); }
  }

  async function verify() {
    if (!file || !identityId) return;
    const id = `att_${crypto.randomUUID().slice(0, 12)}`;
    attempt.current = id;
    setRes(null);
    setError(null);
    setStage(0);
    try {
      const f = new FormData();
      f.append('identity_id', identityId);
      f.append('audio', file);
      f.append('attempt_id', id);
      if (expected) f.append('expected', expected);
      setStage(1);
      const r = await postForm('speakers/verify', f);
      if (attempt.current !== id || (r.attempt_id && r.attempt_id !== id)) return; // a newer attempt started: drop this response
      setStage(4);
      setRes(r);
    } catch (e: any) {
      if (attempt.current === id) setError({ msg: e.message, reportId: e.reportId });
    } finally {
      if (attempt.current === id) setTimeout(() => setStage(-1), 400);
    }
  }

  const outcome = res?.verification_outcome;
  const heroOutcome = res?.test_status === 'ERROR' ? 'ERROR' : HERO[outcome] ?? 'HOLD_FOR_VERIFICATION';
  return (
    <div className="flex flex-col gap-5">
      <RegionHero region="voice" icon={PAGE_ICON.speakers} title="Speaker verification" explain="speaker"
        subtitle="Is this recording the enrolled person? DetectifAI compares it with that person's voiceprint. Deepfake detection runs as separate evidence." />

      <Step n={1} title="Select or enroll a speaker" done={!!ident?.speaker_enrolled}>
        <div className="flex flex-wrap items-end gap-3">
          <label className="label min-w-[240px]">
            Person
            <select className="input" value={identityId} onChange={(e) => setIdentityId(e.target.value)}>
              {ids.map((i) => <option key={i.id} value={i.id}>{i.name}{i.added ? ' · added' : ''}{i.speaker_enrolled ? ' · voiceprint ✓' : ''}</option>)}
            </select>
          </label>
          <label className="label">
            or add a new person
            <span className="flex gap-2">
              <input className="input" placeholder="Full name" value={newName} onChange={(e) => setNewName(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && newName.trim() && create()} />
              <select className="input" aria-label="Use case" value={newUc} onChange={(e) => setNewUc(e.target.value)}>
                {USE_CASES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </span>
          </label>
          <button className="btn" disabled={!newName.trim()} onClick={create}><UserPlus size={15} /> Add</button>
        </div>
        {ident && (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className={`chip ${ident.speaker_enrolled ? 'st-pass' : 'st-hold'}`}><Fingerprint size={12} /> {ident.speaker_enrolled ? 'voiceprint enrolled' : 'not enrolled'}</span>
            {ident.speaker_enrolled && <span className="chip mono">DetectifAI speaker_id {ident.speaker_id}</span>}
            {ident.speaker_enrolled && (
              <button className="btn btn-ghost !py-1 text-[13px]" onClick={() => setShowEnroll((s) => !s)}>{showEnroll ? 'Hide re-enroll' : 'Re-enroll (replaces voiceprint)'}</button>
            )}
            {ident.added && <button className="btn btn-danger ml-auto !py-1 text-[13px]" onClick={remove}><Trash2 size={13} /> Delete person</button>}
          </div>
        )}
        <AnimatePresence initial={false}>
          {identityId && showEnroll && (
            <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
              <div className="mt-4 border-t border-[var(--line)] pt-4"><QuickEnroll key={identityId} identityId={identityId} name={ident?.name} onEnrolled={load} /></div>
            </motion.div>
          )}
        </AnimatePresence>
      </Step>

      <Step n={2} title="Upload or record a new voice sample" done={!!file}>
        <AudioPicker file={file} onFile={setFile} autoPickNew recordHint="Speak for 5–10 s, then press Stop." />
        <fieldset className="mt-4">
          <legend className="mb-1.5 text-[12px] font-semibold text-[var(--ink2)]">What do you expect? (optional — the test is then judged against your label)</legend>
          <div className="tabs">
            {[['', 'Not specified'], ['same_person', 'Same person'], ['different_person', 'Different person']].map(([v, l]) => (
              <button key={v} className={`tab !py-1 ${expected === v ? 'tab-active' : ''}`} aria-pressed={expected === v} onClick={() => setExpected(v)}>{l}</button>
            ))}
          </div>
        </fieldset>
      </Step>

      <Step n={3} title="Run verification" done={!!res}>
        <div className="flex flex-wrap items-center gap-3">
          <button className="btn btn-primary !px-5 !py-2.5" disabled={!file || !ident?.speaker_enrolled || stage >= 0} onClick={verify}>
            <Play size={15} /> Verify against {ident?.name?.split(' (')[0] ?? '…'}
          </button>
          {ident && !ident.speaker_enrolled && <span className="text-sm text-[var(--warn)]">Enroll a voiceprint first (step 1).</span>}
          <span className="text-xs text-[var(--ink3)]">1–2 DetectifAI checks (speaker, plus deepfake when over 4 s)</span>
        </div>
        {stage >= 0 && <div className="mt-3"><Progress stages={STAGES} current={stage} /></div>}
        {error && <div className="mt-3"><ErrorBanner error={error.msg} reportId={error.reportId} onRetry={verify} /></div>}
      </Step>

      <AnimatePresence>
        {res && (
          <motion.div key={res.attempt_id ?? 'r'} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="flex flex-col gap-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-[var(--ink2)]"><StepDot n={4} done /> Result & report</div>
            {res.status === 'NOT_ENROLLED' ? <ErrorBanner error={res.detail} reportId={res.report_id} /> : (
              <>
                <ResultHero outcome={heroOutcome} kind="Speaker verification outcome (not a policy decision)"
                  headline={({ MATCH: 'Match confirmed', NO_MATCH: 'Speaker mismatch detected', INCONCLUSIVE: 'Inconclusive — too close to the threshold', NOT_VERIFIED: 'Could not verify' } as Record<string, string>)[outcome]}
                  title={`${res.identity?.name} · attempt ${res.attempt_id}`} reportId={res.report_id}>
                  {res.test_status && <span className="chip">test: {res.test_status}{expected ? ` vs “${expected.replace('_', ' ')}”` : ''}</span>}
                </ResultHero>
                <div className="grid gap-4 lg:grid-cols-2">
                  <SpeakerCompare claimed={res.identity?.name} speakerId={res.identity?.speaker_id} p={res.speaker_result} findingStatus={res.speaker_agent_finding?.status} />
                  <VoiceMeter p={res.deepfake_result} />
                </div>
                <p className="text-xs text-[var(--ink3)]">A voiceprint match never proves the audio is human — a clone can match. That is why the deepfake check is shown separately.</p>
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function StepDot({ n, done }: { n: number; done?: boolean }) {
  return (
    <span className={`grid size-7 shrink-0 place-items-center rounded-full text-xs font-bold transition-colors ${done ? 'bg-[var(--good)] text-white' : 'bg-[var(--accent-soft)] text-[var(--accent)]'}`}>
      {done ? '✓' : n}
    </span>
  );
}

function Step({ n, title, done, children }: { n: number; title: string; done?: boolean; children: React.ReactNode }) {
  return (
    <motion.section initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: n * 0.05 }} className="panel">
      <h2 className="mb-3 flex items-center gap-2.5 font-semibold"><StepDot n={n} done={done} /> {title}</h2>
      {children}
    </motion.section>
  );
}
