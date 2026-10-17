'use client';
import { useEffect, useRef, useState } from 'react';
import { api, postForm } from '@/lib/api';

const FRAMES = 5;

export default function ExamLive({ onResult }: { onResult: (r: any) => void }) {
  const [ids, setIds] = useState<any[]>([]);
  const [identityId, setIdentityId] = useState('id-rahul');
  const [consent, setConsent] = useState(false);
  const [camOn, setCamOn] = useState(false);
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');
  const [result, setResult] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [auto, setAuto] = useState(false);
  const [threshold, setThreshold] = useState(0.363);
  const [newName, setNewName] = useState('');
  async function createStudent() {
    const form = new FormData();
    form.append('name', newName + ' (student)');
    form.append('use_case', 'exam');
    try {
      const r = await postForm('identities', form);
      setNewName('');
      await load();
      setIdentityId(r.id);
    } catch (e: any) {
      setError(e.message);
    }
  }
  const video = useRef<HTMLVideoElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);

  const load = () => api('identities').then((l) => setIds(l.filter((i: any) => i.use_case === 'exam')));
  useEffect(() => {
    load();
  }, []);
  const ident = ids.find((i) => i.id === identityId);

  async function startCam() {
    setError('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
      if (video.current) {
        video.current.srcObject = stream;
        await video.current.play();
      }
      setCamOn(true);
    } catch (e: any) {
      setError(`Camera unavailable (${e.name || e.message}). Allow camera access in Chrome, or upload images instead.`);
    }
  }

  const snap = (): Promise<Blob> =>
    new Promise((resolve) => {
      const v = video.current!;
      const c = canvas.current!;
      c.width = v.videoWidth;
      c.height = v.videoHeight;
      c.getContext('2d')!.drawImage(v, 0, 0);
      c.toBlob((b) => resolve(b!), 'image/jpeg', 0.92);
    });

  async function enrollReference(file?: Blob) {
    setError('');
    setBusy('enroll');
    try {
      const f = new FormData();
      f.append('consent', String(consent));
      f.append('image', file ?? (await snap()), 'reference.jpg');
      const r = await postForm(`identities/${identityId}/face`, f);
      setMsg(`Reference enrolled (detection score ${r.detection_score.toFixed(2)}). Only the embedding is stored — not the image.`);
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy('');
    }
  }

  async function verify(files?: File[]) {
    setError('');
    setBusy('verify');
    try {
      const f = new FormData();
      f.append('identity_id', identityId);
      f.append('threshold', String(threshold));
      if (files?.length) files.forEach((x) => f.append('frames', x));
      else
        for (let i = 0; i < FRAMES; i++) {
          f.append('frames', await snap(), `frame${i}.jpg`);
          await new Promise((r) => setTimeout(r, 700));
        }
      const r = await postForm('exam/verify', f);
      onResult(r);
      setHistory((h) => [{ at: new Date(), outcome: r.decision.outcome, status: r.findings.find((x: any) => x.finding_type === 'exam_identity')?.status }, ...h]);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy('');
    }
  }

  useEffect(() => {
    if (!auto || !camOn) return;
    const id = setInterval(() => verify(), 60000); // periodic, privacy-conscious re-verification
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auto, camOn, identityId]);

  return (
    <div className="flex flex-col gap-5">
            <div className="grid gap-4 lg:grid-cols-3">
        <section className="panel flex flex-col gap-3 lg:col-span-2">
          <div className="flex flex-wrap items-end gap-3">
            <label className="label">
              Student
              <select className="input" value={identityId} onChange={(e) => setIdentityId(e.target.value)}>
                {ids.map((i) => (
                  <option key={i.id} value={i.id}>
                    {i.name} {i.added ? '· added' : ''} {i.face_reference_enrolled ? '· reference ✓' : '· no reference'}
                  </option>
                ))}
              </select>
            </label>
            <label className="label">
              …or add yourself / anyone as a student
              <span className="flex gap-2">
                <input className="input" placeholder="Name" value={newName} onChange={(e) => setNewName(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && newName.trim() && createStudent()} />
                <button className="btn" disabled={!newName.trim()} onClick={createStudent}>Add to database</button>
              </span>
            </label>
            {ident?.added && (
              <button
                className="btn text-red-600"
                onClick={async () => {
                  try {
                    await api(`identities/${identityId}`, { method: 'DELETE' });
                    setIdentityId('id-rahul');
                    setMsg('Student and face embedding deleted.');
                    load();
                  } catch (e: any) {
                    setError(e.message);
                  }
                }}
              >
                Delete this student
              </button>
            )}
            {!camOn && (
              <button className="btn" onClick={startCam}>
                Turn on camera (asks permission)
              </button>
            )}
          </div>
          <video ref={video} className={`w-full max-w-lg rounded-none border-2 border-[var(--ink)] ${camOn ? '' : 'hidden'}`} muted playsInline />
          <canvas ref={canvas} className="hidden" />

          <h2 className="font-semibold">1 · Consent-based reference enrollment</h2>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
            <span>I am this student and consent to a face reference being used only for this exam session (stored as an embedding; the image is discarded).</span>
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <button className="btn" disabled={!consent || !camOn || !!busy} onClick={() => enrollReference()}>
              Capture reference from camera
            </button>
            <span className="text-xs text-[var(--ink2)]">or upload:</span>
            <input type="file" accept="image/*" className="text-xs" disabled={!consent} onChange={(e) => e.target.files?.[0] && enrollReference(e.target.files[0])} />
          </div>
          {msg && <p className="text-sm text-teal-700">{msg}</p>}
          {ident?.face_reference_enrolled && (
            <button
              className="btn w-fit text-red-600"
              onClick={async () => {
                try {
                  await api(`identities/${identityId}/face`, { method: 'DELETE' });
                  setMsg('Reference embedding and related face results deleted.');
                  load();
                } catch (e: any) {
                  setError(e.message);
                }
              }}
            >
              Delete enrolled reference
            </button>
          )}

          <label className="label max-w-md">
            Match threshold (cosine): {threshold.toFixed(3)} {threshold === 0.363 ? '— OpenCV published default' : '— custom'}
            <input type="range" min={0.2} max={0.7} step={0.001} value={threshold} onChange={(e) => setThreshold(Number(e.target.value))} />
          </label>
          <h2 className="font-semibold">2 · Pre-exam verification ({FRAMES} frames) and periodic re-checks</h2>
          <div className="flex flex-wrap items-center gap-2">
            <button className="btn btn-primary" disabled={!camOn || !!busy} onClick={() => verify()}>
              {busy === 'verify' ? 'Verifying…' : `Verify with ${FRAMES} live frames`}
            </button>
            <span className="text-xs text-[var(--ink2)]">or upload one or more observed images:</span>
            <input type="file" accept="image/*" multiple className="text-xs" onChange={(e) => e.target.files?.length && verify(Array.from(e.target.files))} />
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} disabled={!camOn} /> re-verify every 60 s during the exam
            </label>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
        </section>
        <section className="panel">
          <h2 className="font-semibold">Exam integrity log</h2>
          {!history.length && <p className="mt-2 text-sm text-[var(--ink2)]">No checks yet.</p>}
          {history.map((h, i) => (
            <div key={i} className="mt-2 border-t border-[var(--line)] pt-2 text-sm">
              <span className="text-[var(--ink2)]">{h.at.toLocaleTimeString()}</span> · <b>{h.status}</b>
              <div className="text-xs">{h.outcome}</div>
            </div>
          ))}
          <h3 className="mt-4 text-sm font-semibold">Human review</h3>
          <p className="text-xs text-[var(--ink2)]">Any mismatch, multiple faces or inconclusive result is routed to a proctor with the per-frame evidence below. The student is not marked as cheating.</p>
        </section>
      </div>
    </div>
  );
}
