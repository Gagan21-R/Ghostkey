'use client';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { PageHeader } from '@/components/ui';
import { PAGE_ICON } from '@/lib/icons';

export default function SettingsPage() {
  const [s, setS] = useState<any>(null);
  const [status, setStatus] = useState<any>(null);
  const [error, setError] = useState('');
  const load = () => {
    setError('');
    api('settings').then(setS).catch((e) => setError(e.message));
    api('provider/status').then(setStatus).catch(() => {});
  };
  useEffect(() => { load(); }, []);
  if (error) return <p className="text-red-600">{error} <button className="btn ml-2" onClick={load}>Retry</button></p>;
  if (!s) return <p className="text-[var(--ink2)]">Loading…</p>;
  const Row = ({ k, v }: { k: string; v: any }) => (
    <tr className="border-t border-[var(--line)]"><td className="py-1.5 pr-4 text-[var(--ink2)]">{k}</td><td>{typeof v === 'string' ? v : JSON.stringify(v)}</td></tr>
  );
  return (
    <div className="flex flex-col gap-4">
      <PageHeader icon={PAGE_ICON.settings} title="Settings & configuration" explain="status" subtitle="Read-only status. Secrets stay in backend/.env and never reach the browser." />
      <section className="panel">
        <h2 className="mb-2 font-semibold">DetectifAI</h2>
        <table className="w-full text-sm"><tbody>
          <Row k="API key configured" v={s.detectifai.api_key_configured ? 'yes (value hidden)' : 'NO — set DETECTIF_API_KEY in backend/.env'} />
          <Row k="Env variable names" v={s.detectifai.api_key_env_vars.join(' or ')} />
          <Row k="Base URL" v={s.detectifai.base_url} />
          <Row k="Health" v={status?.health?.reachable ? `reachable (${status.health.status})` : status ? `unreachable: ${status.health?.error}` : '…'} />
          <Row k="Credits" v={status?.credits?.available !== undefined ? `${status.credits.available} available · ${status.credits.price_per_operation} per check · plan ${status.credits.plan}` : status?.credits?.error ?? '…'} />
          <Row k="Scopes" v={s.detectifai.scopes_note} />
          {Object.entries(s.detectifai.capabilities).map(([k, v]) => <Row key={k} k={`capability: ${k}`} v={v} />)}
        </tbody></table>
      </section>
      <section className="panel">
        <h2 className="mb-2 font-semibold">Platform</h2>
        <table className="w-full text-sm"><tbody>
          <Row k="Face model" v={`${s.face_model.name} · cosine threshold ${s.face_model.threshold} · ${s.face_model.available ? 'loaded' : 'MISSING'}`} />
          <Row k="Uploads" v={`audio ≤ ${s.uploads.max_audio_mb} MB, images ≤ ${s.uploads.max_image_mb} MB, stored on disk: ${s.uploads.stored_on_disk ? 'yes' : 'no'}`} />
          <Row k="Case retention" v={`${s.retention.case_retention_days} days (GHOSTKEY_CASE_RETENTION_DAYS)`} />
          <Row k="Biometrics" v={s.retention.biometrics} />
          <Row k="Database" v={`${s.database.engine} — MongoDB: ${s.database.mongodb}`} />
          <Row k="Internal API token" v={s.internal_api_token_configured ? 'custom token set' : 'using the dev default — set GHOSTKEY_API_TOKEN before deploying'} />
          <Row k="LLM" v={s.llm} />
          <Row k="n8n" v={s.n8n} />
          <Row k="Trusted device" v={s.trusted_device} />
        </tbody></table>
      </section>
    </div>
  );
}
