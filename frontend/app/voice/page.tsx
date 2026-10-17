'use client';
import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { AudioWaveform, Play } from 'lucide-react';
import { PAGE_ICON } from '@/lib/icons';
import { postForm } from '@/lib/api';
import AudioPicker from '@/components/AudioPicker';
import RegionHero from '@/components/RegionHero';
import { Card, ErrorBanner, Progress, ResultHero, VoiceMeter } from '@/components/viz';

const STAGES = ['Validating audio', 'Submitting to DetectifAI', 'Processing provider response', 'Saving test report'];
const HERO: Record<string, string> = { real: 'VERIFIED_AND_AUTHORIZED', fake: 'DENIED', not_sure: 'HOLD_FOR_VERIFICATION' };

export default function VoicePage() {
  const [file, setFile] = useState<File | null>(null);
  const [expected, setExpected] = useState('');
  const [res, setRes] = useState<any>(null);
  const [stage, setStage] = useState(-1);
  const [error, setError] = useState<{ msg: string; reportId?: string } | null>(null);
  const attempt = useRef(0);
  useEffect(() => { setRes(null); setError(null); }, [file, expected]);

  async function analyze() {
    if (!file) return;
    const n = ++attempt.current;
    setStage(0);
    setError(null);
    setRes(null);
    try {
      const form = new FormData();
      form.append('audio', file);
      if (expected) form.append('expected', expected);
      setStage(1);
      const r = await postForm('audio/analyze', form);
      if (n !== attempt.current) return;
      setStage(4);
      setRes(r);
    } catch (e: any) {
      if (n === attempt.current) setError({ msg: e.message, reportId: e.reportId });
    } finally {
      if (n === attempt.current) setTimeout(() => setStage(-1), 400);
    }
  }

  const p = res?.provider_result;
  const ran = p && ['COMPLETED', 'INCONCLUSIVE'].includes(p.status);
  const segs = p?.details?.segments ?? [];
  const failedHard = p && !ran && p.status === 'UNAVAILABLE';
  return (
    <div className="flex flex-col gap-5">
      <RegionHero region="voice" icon={PAGE_ICON.voice} title="Voice analysis" explain="voice" subtitle="Is this voice AI-generated? Sent to DetectifAI's deepfake model (1 check). Nothing is stored on disk." />
      <section className="panel flex flex-col gap-3">
        <h2 className="font-semibold">Pick a recording</h2>
        <AudioPicker file={file} onFile={setFile} autoPickNew />
        <div className="flex flex-wrap items-center gap-3">
          <div className="tabs" role="group" aria-label="Expected result">
            {[['', 'Expectation: none'], ['real_human', 'Real human'], ['ai_voice', 'AI-generated']].map(([v, l]) => (
              <button key={v} className={`tab !py-1 ${expected === v ? 'tab-active' : ''}`} aria-pressed={expected === v} onClick={() => setExpected(v)}>{l}</button>
            ))}
          </div>
          <button className="btn btn-primary !px-5" disabled={!file || stage >= 0} onClick={analyze}><Play size={15} /> Analyse with DetectifAI</button>
          <span className="text-xs text-[var(--ink3)]">more than 4 s, at most 120 s · up to 25 MB</span>
        </div>
        {stage >= 0 && <Progress stages={STAGES} current={stage} />}
        {error && <ErrorBanner error={error.msg} reportId={error.reportId} onRetry={analyze} />}
      </section>

      <AnimatePresence>
        {res && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="flex flex-col gap-4">
            <ResultHero outcome={ran ? HERO[p.classification] ?? 'HOLD_FOR_VERIFICATION' : failedHard ? 'ERROR' : 'HOLD_FOR_VERIFICATION'}
              kind="Deepfake detection result (not an identity check)"
              headline={ran ? ({ real: 'No synthetic indicators', fake: 'Synthetic (AI-generated) indicators', not_sure: 'Inconclusive' } as Record<string, string>)[p.classification] : `Could not analyse: ${p?.error}`}
              title={file?.name} reportId={res.report_id}>
              <span className={`chip ${p?.simulated ? 'st-hold' : 'st-pass'}`}>{p?.simulated ? 'SIMULATED' : 'Real DetectifAI output'}</span>
            </ResultHero>
            <div className="grid gap-4 lg:grid-cols-2">
              <VoiceMeter p={p} />
              <Card icon={AudioWaveform} title="Per-segment scores" sub="from DetectifAI's response">
                {segs.length ? (
                  <div className="flex h-28 items-end gap-1">
                    {segs.map((s: any, i: number) => {
                      const bad = s.score >= (p.threshold ?? 0.62);
                      return (
                        <div key={i} className="flex h-full flex-1 flex-col items-center justify-end gap-1">
                          <motion.div initial={{ height: 0 }} animate={{ height: `${Math.max(4, s.score * 100)}%` }} transition={{ delay: i * 0.04 }}
                            className="w-full rounded-none" style={{ background: bad ? 'var(--bad)' : 'var(--good)' }} title={`${s.start}–${s.end}s: ${s.score.toFixed(3)}`} />
                          <span className="text-[9.5px] text-[var(--ink3)]">{s.start}s</span>
                        </div>
                      );
                    })}
                  </div>
                ) : <span className="text-sm text-[var(--ink3)]">No segment scores returned.</span>}
                <div className="mono mt-2 text-[var(--ink3)]">request {p?.details?.request_id ?? '—'} · operation {p?.raw_result_reference ?? '—'} · model {p?.details?.model ? `${p.details.model.name} ${p.details.model.version}` : '—'}</div>
                <div className="mt-1 text-xs text-[var(--ink2)]">Agent: <b>{res.voice_agent_finding?.status?.replaceAll('_', ' ').toLowerCase()}</b> → {res.voice_agent_finding?.recommended_next_step}</div>
              </Card>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
