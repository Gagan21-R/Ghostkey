'use client';
import { useState } from 'react';
import { BadgeCheck, Fingerprint, Loader2, Timer } from 'lucide-react';
import { postForm } from '@/lib/api';
import { toWav } from '@/lib/audio';
import AudioPicker from './AudioPicker';
import { ErrorBanner, ReportButton } from './viz';

/** Voiceprint enrollment from about 10 s of speech, recorded with manual start/stop. The backend repeats a sample
 * shorter than DetectifAI's 15 s minimum up to that length and says so. */
export default function QuickEnroll({ identityId, name, onEnrolled, compact = false }: { identityId: string; name?: string; onEnrolled?: (r: any) => void; compact?: boolean }) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<any>(null);
  const [error, setError] = useState<{ msg: string; reportId?: string } | null>(null);

  async function enroll() {
    if (!file) return;
    setBusy(true);
    setError(null);
    setRes(null);
    try {
      // always WAV, so the backend can measure the length and extend a short sample
      const wav = await toWav(file).then((w) => w.file).catch(() => file);
      const f = new FormData();
      f.append('audio', wav);
      const r = await postForm(`identities/${identityId}/voice`, f);
      setRes(r);
      onEnrolled?.(r);
    } catch (e: any) {
      setError({ msg: e.message, reportId: e.reportId });
    } finally {
      setBusy(false);
    }
  }

  const q = res?.quality && typeof res.quality === 'object' ? Object.entries(res.quality).filter(([, v]) => typeof v !== 'object') : [];
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2 rounded-none border border-sky-500/25 bg-sky-500/5 px-3 py-2 text-[12.5px] text-blue-700">
        <Timer size={14} className="shrink-0 text-blue-600" />
        <span>Press Record, speak for <b>about 10 seconds</b>, then press Stop — e.g. &quot;My name is {name?.split(' (')[0] || '…'} and this is my voice. I am enrolling it for the GhostKey demo.&quot;</span>
      </div>
      <AudioPicker file={file} onFile={setFile} recordSeconds={60} recordHint="Starts and stops only when you press the button — speak for about 10 s (max 60 s)." compact={compact} />
      <button className="btn btn-primary w-fit" disabled={!file || !identityId || busy} onClick={enroll}>
        {busy ? <Loader2 size={15} className="animate-spin" /> : <Fingerprint size={15} />} {busy ? 'Enrolling with DetectifAI…' : 'Enroll voiceprint'}
      </button>
      {error && <ErrorBanner error={error.msg} reportId={error.reportId} />}
      {res?.ok && (
        <div className="fade-in rounded-none border border-emerald-500/35 bg-emerald-500/[0.07] p-3 text-sm">
          <div className="flex items-center gap-2 font-semibold text-teal-700"><BadgeCheck size={17} /> Voiceprint enrolled for {res.name}</div>
          <div className="mt-2 grid grid-cols-2 gap-2 text-[12.5px] sm:grid-cols-4">
            <Stat k="Recorded" v={res.recorded_seconds ? `${res.recorded_seconds.toFixed(1)} s` : 'checked by DetectifAI'} />
            <Stat k="Sent to DetectifAI" v={res.looped_to_seconds ? `${res.looped_to_seconds.toFixed(0)} s (repeated)` : 'as recorded'} />
            <Stat k="Speaker id" v={res.speaker_id} mono />
            <Stat k="Operation" v={res.operation_id ?? '—'} mono />
            {q.map(([k, v]) => <Stat key={k} k={k.replaceAll('_', ' ')} v={String(v)} />)}
          </div>
          {res.note && <p className="mt-2 text-[11.5px] text-amber-800">{res.note}</p>}
          {res.replaced_previous && <p className="mt-2 text-[11.5px] text-[var(--ink2)]">The previous voiceprint was replaced (not blended with this sample).</p>}
          <div className="mt-2"><ReportButton id={res.report_id} className="!py-1 text-[13px]" /></div>
          <p className="mt-1 text-[11.5px] text-[var(--ink2)]">Real DetectifAI enrollment. A voiceprint match never proves the audio is human — a clone can match, so the deepfake check always runs too.</p>
        </div>
      )}
    </div>
  );
}

const Stat = ({ k, v, mono }: { k: string; v: string; mono?: boolean }) => (
  <div className="rounded-none bg-[var(--panel2)] px-2 py-1.5">
    <div className="text-[10.5px] uppercase tracking-wide text-[var(--ink2)]">{k}</div>
    <div className={`truncate ${mono ? 'mono' : ''}`} title={v}>{v}</div>
  </div>
);
