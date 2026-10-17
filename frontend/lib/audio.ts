// Browser-side audio helpers: decode anything Chrome can play (MP4/WhatsApp audio, WebM recordings…)
// and re-encode it as 16 kHz mono WAV, so the backend can measure the duration before spending credits.

export const NATIVE_EXT = ['.wav', '.mp3', '.flac', '.ogg', '.opus', '.oga', '.webm', '.m4a', '.aac', '.aiff', '.aif'];
export const ACCEPT_AUDIO = 'audio/*,video/mp4,video/3gpp,.wav,.mp3,.flac,.ogg,.opus,.oga,.webm,.m4a,.aac,.aiff,.aif,.mp4,.3gp';

export const ext = (name: string) => (name.match(/\.[^.]+$/)?.[0] ?? '').toLowerCase();

async function decode(file: Blob): Promise<AudioBuffer> {
  const Ctx = window.AudioContext || (window as any).webkitAudioContext;
  const ctx: AudioContext = new Ctx();
  try {
    return await ctx.decodeAudioData(await file.arrayBuffer());
  } finally {
    ctx.close();
  }
}

function encodeWav(samples: Float32Array, rate: number): Blob {
  const buf = new ArrayBuffer(44 + samples.length * 2);
  const v = new DataView(buf);
  const str = (o: number, s: string) => [...s].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)));
  str(0, 'RIFF');
  v.setUint32(4, 36 + samples.length * 2, true);
  str(8, 'WAVE');
  str(12, 'fmt ');
  v.setUint32(16, 16, true);
  v.setUint16(20, 1, true); // PCM
  v.setUint16(22, 1, true); // mono
  v.setUint32(24, rate, true);
  v.setUint32(28, rate * 2, true);
  v.setUint16(32, 2, true);
  v.setUint16(34, 16, true);
  str(36, 'data');
  v.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    v.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([buf], { type: 'audio/wav' });
}

/** Decode and re-encode as 16 kHz mono WAV. Throws if the browser cannot decode the file. */
export async function toWav(file: File, rate = 16000): Promise<{ file: File; seconds: number }> {
  const decoded = await decode(file);
  const off = new OfflineAudioContext(1, Math.max(1, Math.ceil(decoded.duration * rate)), rate);
  const src = off.createBufferSource();
  src.buffer = decoded;
  src.connect(off.destination);
  src.start();
  const mono = (await off.startRendering()).getChannelData(0);
  const name = file.name.replace(/\.[^.]+$/, '') + '.wav';
  return { file: new File([encodeWav(mono, rate)], name, { type: 'audio/wav' }), seconds: decoded.duration };
}

/** Rough energy-based estimate of how many seconds contain speech (20 ms frames well above the noise floor).
 * Only a pre-check to catch a muted or wrong microphone before spending credits; DetectifAI decides for real. */
export function speechSeconds(buf: AudioBuffer): { speech: number; peak: number } {
  const data = buf.getChannelData(0);
  const n = Math.max(1, Math.floor(buf.sampleRate * 0.02));
  const rms: number[] = [];
  let peak = 0;
  for (let i = 0; i + n <= data.length; i += n) {
    let sum = 0;
    for (let j = i; j < i + n; j++) {
      sum += data[j] * data[j];
      peak = Math.max(peak, Math.abs(data[j]));
    }
    rms.push(Math.sqrt(sum / n));
  }
  const floor = [...rms].sort((a, b) => a - b)[Math.floor(rms.length * 0.1)] ?? 0;
  const thr = Math.max(0.01, floor * 4);
  return { speech: rms.filter((r) => r > thr).length * 0.02, peak };
}

export type Prepared = { file: File; seconds: number | null; speech: number | null; peak: number | null; convertedFrom?: string };

/** Files DetectifAI reads directly are sent unchanged; others (MP4, 3GP…) are converted to WAV in the browser. */
export async function prepareAudio(file: File): Promise<Prepared> {
  const decoded = await decode(file).catch(() => null);
  const st = decoded ? speechSeconds(decoded) : null;
  const base = { seconds: decoded?.duration ?? null, speech: st?.speech ?? null, peak: st?.peak ?? null };
  if (NATIVE_EXT.includes(ext(file.name)) || !decoded) return { file, ...base }; // the backend forwards MP4 as M4A
  try {
    const w = await toWav(file);
    return { ...base, file: w.file, convertedFrom: ext(file.name).slice(1).toUpperCase() || file.type };
  } catch {
    return { file, ...base };
  }
}

export const fmtBytes = (b: number) => (b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1e3))} KB`);
export const fmtAge = (s: number) => (s < 60 ? 'just now' : s < 3600 ? `${Math.round(s / 60)} min ago` : s < 86400 ? `${Math.round(s / 3600)} h ago` : `${Math.round(s / 86400)} d ago`);
