'use client';
import { useEffect, useRef, useState } from 'react';

const MIC_KEY = 'ghostkey-mic';

// Consent-gated microphone recording (MediaRecorder → WebM/Opus, which DetectifAI accepts), with a microphone
// picker and a live level meter so a muted / wrong input is visible before anything is sent.
export default function Recorder({ onRecorded, maxSeconds = 30, hint = 'Speak for at least 5 seconds (deepfake check needs more than 4 s).' }: { onRecorded: (f: File) => void; maxSeconds?: number; hint?: string }) {
  const [consent, setConsent] = useState(false);
  const [state, setState] = useState<'idle' | 'recording'>('idle');
  const [secs, setSecs] = useState(0);
  const [error, setError] = useState('');
  const [mics, setMics] = useState<MediaDeviceInfo[]>([]);
  const [micId, setMicId] = useState('');
  const [level, setLevel] = useState(0);
  const [heard, setHeard] = useState(false);
  const rec = useRef<MediaRecorder | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const raf = useRef(0);
  const ctx = useRef<AudioContext | null>(null);

  const listMics = () =>
    navigator.mediaDevices?.enumerateDevices().then((d) => {
      const inputs = d.filter((x) => x.kind === 'audioinput' && x.deviceId);
      setMics(inputs);
      let saved = '';
      try { saved = localStorage.getItem(MIC_KEY) ?? ''; } catch {}
      setMicId((cur) => cur || (inputs.some((i) => i.deviceId === saved) ? saved : ''));
    }).catch(() => {});
  useEffect(() => {
    listMics();
    navigator.mediaDevices?.addEventListener?.('devicechange', listMics);
    return () => {
      navigator.mediaDevices?.removeEventListener?.('devicechange', listMics);
      cancelAnimationFrame(raf.current);
      ctx.current?.close().catch(() => {});
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function start() {
    setError('');
    setHeard(false);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { deviceId: micId ? { exact: micId } : undefined, channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      listMics(); // device names are only visible after permission is granted
      // live level meter
      const ac = new AudioContext();
      ctx.current = ac;
      const an = ac.createAnalyser();
      an.fftSize = 1024;
      ac.createMediaStreamSource(stream).connect(an);
      const buf = new Float32Array(an.fftSize);
      const tick = () => {
        an.getFloatTimeDomainData(buf);
        let sum = 0;
        for (const v of buf) sum += v * v;
        const rms = Math.sqrt(sum / buf.length);
        setLevel(Math.min(1, rms * 8));
        if (rms > 0.02) setHeard(true);
        raf.current = requestAnimationFrame(tick);
      };
      tick();

      const mr = new MediaRecorder(stream);
      const chunks: Blob[] = [];
      mr.ondataavailable = (e) => chunks.push(e.data);
      mr.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        cancelAnimationFrame(raf.current);
        ac.close().catch(() => {});
        setLevel(0);
        const type = mr.mimeType || 'audio/webm';
        onRecorded(new File([new Blob(chunks, { type })], `recording.${type.includes('ogg') ? 'ogg' : 'webm'}`, { type }));
      };
      mr.start();
      rec.current = mr;
      setSecs(0);
      setState('recording');
      timer.current = setInterval(() => setSecs((s) => {
        if (s + 1 >= maxSeconds) stop();
        return s + 1;
      }), 1000);
    } catch (e: any) {
      setError(
        e?.name === 'NotAllowedError' ? 'Microphone permission denied. Allow it in the address bar (Chrome), or upload a file.'
          : e?.name === 'OverconstrainedError' || e?.name === 'NotFoundError' ? 'That microphone is not available — pick another one.'
            : `Microphone unavailable: ${e?.message ?? e}`,
      );
    }
  }
  function stop() {
    if (timer.current) clearInterval(timer.current);
    rec.current?.state === 'recording' && rec.current.stop();
    setState('idle');
  }

  return (
    <div className="flex flex-col gap-2 text-sm">
      <label className="flex items-start gap-2">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        <span>The speaker consents to this recording being analysed (DetectifAI) for this demo.</span>
      </label>
      {mics.length > 1 && (
        <select
          className="input !py-1 text-xs"
          value={micId}
          disabled={state === 'recording'}
          onChange={(e) => { setMicId(e.target.value); try { localStorage.setItem(MIC_KEY, e.target.value); } catch {} }}
        >
          <option value="">Default microphone</option>
          {mics.map((m, i) => <option key={m.deviceId} value={m.deviceId}>{m.label || `Microphone ${i + 1}`}</option>)}
        </select>
      )}
      <div className="flex items-center gap-2">
        {state === 'idle' ? (
          <button className="btn" disabled={!consent} onClick={start}>
            ● Record
          </button>
        ) : (
          <button className="btn btn-primary" onClick={stop}>
            ■ Stop ({secs}s)
          </button>
        )}
        <span className="text-xs text-[var(--ink2)]">{hint}</span>
      </div>
      {state === 'recording' && (
        <div className="flex flex-col gap-1">
          <div className="h-2 overflow-hidden rounded-full bg-slate-200/70">
            <div className="h-full rounded-full transition-[width] duration-75" style={{ width: `${Math.round(level * 100)}%`, background: level > 0.15 ? '#0d9488' : '#d97706' }} />
          </div>
          <span className={`text-[11px] ${heard ? 'text-teal-700' : 'text-amber-700'}`}>
            {heard ? 'Hearing you — keep talking.' : secs >= 2 ? 'No sound yet — check the microphone above, your Windows mic volume, or that the mic is not muted.' : 'Listening…'}
          </span>
        </div>
      )}
      {error && <p className="text-red-600">{error}</p>}
    </div>
  );
}
