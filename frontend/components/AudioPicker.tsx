'use client';
import { useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, Download, FileAudio, FolderDown, Loader2, Mic, RefreshCw, Sparkles, Upload, X } from 'lucide-react';
import { api } from '@/lib/api';
import { ACCEPT_AUDIO, fmtAge, fmtBytes, prepareAudio } from '@/lib/audio';
import Recorder from './Recorder';

type Dl = { name: string; bytes: number; modified: number; age_seconds: number };

/**
 * One audio input for every page: record, drag-and-drop / browse (MP4 WhatsApp audio included), or pick from the
 * newest files in the Downloads folder — refreshed every few seconds, so a file downloaded a moment ago is listed
 * at the top and, with `autoPickNew`, selected automatically.
 */
export default function AudioPicker({
  file, onFile, record = true, recordSeconds = 40, recordHint, autoPickNew = false, compact = false,
}: {
  file: File | null; onFile: (f: File | null) => void; record?: boolean; recordSeconds?: number; recordHint?: string; autoPickNew?: boolean; compact?: boolean;
}) {
  const [downloads, setDownloads] = useState<{ enabled: boolean; folder: string | null; files: Dl[] } | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [busy, setBusy] = useState('');
  const [meta, setMeta] = useState<{ seconds: number | null; speech: number | null; peak: number | null; convertedFrom?: string; source: string } | null>(null);
  const [notice, setNotice] = useState('');
  const [drag, setDrag] = useState(false);
  const newest = useRef<number | null>(null);
  const url = useMemo(() => (file ? URL.createObjectURL(file) : ''), [file]);
  useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);

  async function choose(raw: File, source: string) {
    setBusy(raw.name);
    try {
      const p = await prepareAudio(raw);
      setMeta({ seconds: p.seconds, speech: p.speech, peak: p.peak, convertedFrom: p.convertedFrom, source });
      onFile(p.file);
    } finally {
      setBusy('');
    }
  }

  async function pickDownload(d: Dl, auto = false) {
    setBusy(d.name);
    try {
      const res = await fetch(`/api/local/downloads/file?name=${encodeURIComponent(d.name)}`, { cache: 'no-store' });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? `HTTP ${res.status}`);
      await choose(new File([await res.blob()], d.name), auto ? 'new download (auto-selected)' : 'Downloads');
      if (auto) setNotice(`New download detected and selected: ${d.name}`);
    } catch (e: any) {
      setNotice(`Could not read ${d.name}: ${e.message}`);
    } finally {
      setBusy('');
    }
  }

  const refresh = () =>
    api('local/downloads').then((d) => {
      setDownloads(d);
      const top: Dl | undefined = d.files[0];
      if (top && newest.current !== null && top.modified > newest.current && autoPickNew) pickDownload(top, true);
      if (top) newest.current = Math.max(newest.current ?? 0, top.modified);
      else if (newest.current === null) newest.current = 0;
    }).catch(() => setDownloads({ enabled: false, folder: null, files: [] }));

  useEffect(() => {
    refresh();
    const id = setInterval(() => document.visibilityState === 'visible' && refresh(), 4000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const files = downloads?.files ?? [];
  const shown = showAll ? files : files.slice(0, compact ? 3 : 4);

  return (
    <div className="flex flex-col gap-3">
      <div className={`grid gap-3 ${record ? 'md:grid-cols-2' : ''}`}>
        {record && (
          <div className="rounded-none border-2 border-[var(--ink)] bg-[var(--panel2)] p-3">
            <div className="mb-2 flex items-center gap-2 text-sm"><Mic size={15} className="text-red-600" /> Record now</div>
            <Recorder maxSeconds={recordSeconds} hint={recordHint} onRecorded={(f) => choose(f, 'microphone')} />
          </div>
        )}
        <label
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files?.[0]; if (f) choose(f, 'dropped file'); }}
          className={`flex cursor-pointer flex-col items-center justify-center gap-1.5 rounded-none border border-dashed p-3 text-center text-sm transition-colors ${drag ? 'border-sky-400 bg-sky-500/10' : 'border-[var(--line-strong)] bg-[var(--panel2)] hover:border-sky-400'}`}
        >
          <Upload size={20} className="text-blue-600" />
          <span>Drop a file here or click to browse</span>
          <span className="text-[11px] text-[var(--ink2)]">WAV, MP3, M4A, MP4 (WhatsApp audio), OGG, WebM, FLAC</span>
          <input type="file" accept={ACCEPT_AUDIO} className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) choose(f, 'browsed file'); e.target.value = ''; }} />
        </label>
      </div>

      {downloads?.enabled && (
        <div className="rounded-none border-2 border-[var(--ink)] bg-[var(--panel2)] p-3">
          <div className="mb-2 flex items-center justify-between gap-2 text-sm">
            <span className="flex items-center gap-2"><FolderDown size={15} className="text-violet-600" /> Latest in Downloads <span className="text-[11px] text-[var(--ink2)]">· live, newest first</span></span>
            <button className="text-[var(--ink2)] hover:text-[var(--ink)]" title="Refresh" onClick={refresh}><RefreshCw size={13} /></button>
          </div>
          {!files.length && <p className="text-xs text-[var(--ink2)]">No audio files in {downloads.folder} yet — download one and it appears here.</p>}
          <ul className="flex flex-col gap-1">
            {shown.map((d) => (
              <li key={d.name}>
                <button
                  disabled={!!busy}
                  onClick={() => pickDownload(d)}
                  className={`flex w-full items-center gap-2 rounded-none px-2 py-1.5 text-left text-[12.5px] transition-colors hover:bg-slate-100 ${file?.name.replace(/\.wav$/, '') === d.name.replace(/\.[^.]+$/, '') ? 'bg-sky-500/10 ring-1 ring-sky-500/40' : ''}`}
                >
                  {busy === d.name ? <Loader2 size={14} className="animate-spin text-blue-600" /> : <Download size={14} className="text-[var(--ink2)]" />}
                  <span className="min-w-0 flex-1 truncate">{d.name}</span>
                  {d.age_seconds < 900 && <span className="rounded-none bg-emerald-500/20 px-1.5 text-[10px] font-semibold text-teal-700">NEW</span>}
                  <span className="shrink-0 text-[11px] text-[var(--ink2)]">{fmtAge(d.age_seconds)} · {fmtBytes(d.bytes)}</span>
                </button>
              </li>
            ))}
          </ul>
          {files.length > shown.length && <button className="mt-1 text-[11.5px] text-blue-600 hover:underline" onClick={() => setShowAll(true)}>Show {files.length - shown.length} more</button>}
        </div>
      )}

      {notice && <p className="flex items-center gap-1.5 text-xs text-teal-700"><Sparkles size={12} /> {notice}</p>}
      {busy && !file && <p className="flex items-center gap-2 text-xs text-[var(--ink2)]"><Loader2 size={12} className="animate-spin" /> Preparing audio…</p>}
      {file && (
        <div className="flex flex-wrap items-center gap-3 rounded-none border border-emerald-500/30 bg-emerald-500/5 p-3 text-sm">
          <FileAudio size={16} className="text-teal-700" />
          <div className="min-w-0">
            <div className="truncate">{file.name}</div>
            <div className="text-[11px] text-[var(--ink2)]">
              {meta?.source}{meta?.seconds ? ` · ${meta.seconds.toFixed(1)} s` : ''}{meta?.speech != null ? ` · ~${meta.speech.toFixed(1)} s of speech` : ''}{meta?.convertedFrom ? ` · converted from ${meta.convertedFrom} to WAV in your browser` : ''}
            </div>
          </div>
          <audio controls src={url} className="h-9 min-w-0 flex-1" />
          <button className="text-[var(--ink2)] hover:text-red-600" title="Clear" onClick={() => { onFile(null); setMeta(null); setNotice(''); }}><X size={16} /></button>
          {meta?.speech != null && meta.speech < 2 && (
            <div className="flex w-full items-start gap-2 rounded-none border border-amber-500/40 bg-amber-500/10 p-2 text-[12px] text-amber-800">
              <AlertTriangle size={14} className="mt-0.5 shrink-0" />
              <span>
                Almost no speech in this file (~{meta.speech.toFixed(1)} s{meta.peak != null ? `, loudest point ${Math.round(meta.peak * 100)}%` : ''}). DetectifAI needs at least 2 s of clear speech, so it will likely reject it.
                {meta.source === 'microphone' && ' Pick the right microphone, raise the Windows mic volume (Settings → System → Sound → Input), speak closer, and record again.'}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
