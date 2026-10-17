'use client';
import { useEffect, useState } from 'react';
import { api, postForm, postJson } from '@/lib/api';
import { ACCEPT_AUDIO } from '@/lib/audio';

export default function FamilyLive({ onResult }: { onResult: (r: any) => void }) {
  const [ids, setIds] = useState<any[]>([]);
  const [identityId, setIdentityId] = useState('id-asha');
  const [caller, setCaller] = useState("Rohan (Asha's son)");
  const [actionType, setActionType] = useState('emergency_transfer');
  const [amount, setAmount] = useState('50000');
  const [transcript, setTranscript] = useState("Ma, it's Rohan. I had an accident, send 50,000 right now, don't tell papa.");
  const [events, setEvents] = useState({ number_reassigned: true, sim_swap_alert: false, recovery_changed: false });
  const [audio, setAudio] = useState<File | null>(null);
  const [session, setSession] = useState<any>(null);
  const [code, setCode] = useState('');
  const [iv, setIv] = useState<any>(null);
  const [result, setResult] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api('identities').then((l) => setIds(l.filter((i: any) => i.use_case === 'family')));
  }, []);
  const ident = ids.find((i) => i.id === identityId);

  const guard = async (fn: () => Promise<void>) => {
    setError('');
    setBusy(true);
    try {
      await fn();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  const sendCode = () =>
    guard(async () => {
      setIv(null);
      setSession(await postJson('sessions', { use_case: 'family', identity_id: identityId, action: { type: actionType, amount: Number(amount) || null } }));
    });
  const checkCode = () =>
    guard(async () => {
      const r = await postJson(`sessions/${session.session_id}/challenge/verify`, { challenge_id: session.challenge.challenge_id, response: code });
      setIv({ method: `code sent to enrolled recovery channel (${ident?.recovery_method})`, status: r.valid ? 'passed' : 'failed', reason: r.reason });
    });
  const investigate = () =>
    guard(async () => {
      const carrier = [
        ...(events.number_reassigned ? [{ type: 'number_reassigned', simulated: true }] : []),
        ...(events.sim_swap_alert ? [{ type: 'sim_swap_alert', simulated: true }] : []),
      ];
      const f = new FormData();
      f.append('use_case', 'family');
      f.append('identity_id', identityId);
      f.append('action', JSON.stringify({ type: actionType, amount: Number(amount) || null, details: { claimed_caller: caller } }));
      f.append('actor_role', 'family_member');
      f.append('transcript', transcript);
      f.append('carrier_events', JSON.stringify(carrier));
      f.append('account_events', JSON.stringify(events.recovery_changed ? [{ type: 'recovery_channel_changed' }] : []));
      f.append('independent_verification', JSON.stringify(iv ?? { method: 'none', status: 'not completed' }));
      if (audio) f.append('audio', audio);
      onResult(await postForm('investigate', f));
    });

  return (
    <div className="flex flex-col gap-5">
            <div className="grid gap-4 lg:grid-cols-3">
        <section className="panel flex flex-col gap-3 lg:col-span-2">
          <h2 className="font-semibold">1 · Protected identity & incoming call</h2>
          <div className="grid gap-3 md:grid-cols-3">
            <label className="label">
              Protected person
              <select className="input" value={identityId} onChange={(e) => setIdentityId(e.target.value)}>
                {ids.map((i) => (
                  <option key={i.id} value={i.id}>
                    {i.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="label">
              Caller claims to be
              <input className="input" value={caller} onChange={(e) => setCaller(e.target.value)} />
            </label>
            <label className="label">
              Request
              <select className="input" value={actionType} onChange={(e) => setActionType(e.target.value)}>
                <option value="emergency_transfer">Emergency money transfer</option>
                <option value="send_money">Routine money request</option>
                <option value="share_otp">Asks for an OTP</option>
                <option value="chat">Just talking</option>
              </select>
            </label>
            <label className="label">
              Amount (₹)
              <input className="input" value={amount} onChange={(e) => setAmount(e.target.value)} />
            </label>
            <label className="label md:col-span-2">
              Caller audio (optional, sent to DetectifAI)
              <input type="file" accept={ACCEPT_AUDIO} className="text-xs" onChange={(e) => setAudio(e.target.files?.[0] ?? null)} />
            </label>
          </div>
          <label className="label">
            What the caller said
            <textarea className="input" rows={2} value={transcript} onChange={(e) => setTranscript(e.target.value)} />
          </label>
          <h2 className="mt-2 font-semibold">2 · Simulated carrier & account events</h2>
          <div className="flex flex-wrap gap-4 text-sm">
            {(
              [
                ['number_reassigned', 'Number deactivated & reassigned'],
                ['sim_swap_alert', 'SIM-swap alert'],
                ['recovery_changed', 'Recovery channel changed recently'],
              ] as const
            ).map(([k, l]) => (
              <label key={k} className="flex items-center gap-2">
                <input type="checkbox" checked={events[k]} onChange={(e) => setEvents({ ...events, [k]: e.target.checked })} /> {l} <span className="chip">SIMULATED</span>
              </label>
            ))}
          </div>
          <h2 className="mt-2 font-semibold">3 · Independent verification</h2>
          <div className="flex flex-wrap items-center gap-2">
            <button className="btn" onClick={sendCode} disabled={busy}>
              Send code to the enrolled recovery channel
            </button>
            {session && (
              <>
                <input className="input w-40" placeholder="code the caller gives" value={code} onChange={(e) => setCode(e.target.value)} />
                <button className="btn" onClick={checkCode} disabled={busy || !code}>
                  Check code
                </button>
              </>
            )}
            {iv && <span className={`chip ${iv.status === 'passed' ? 'text-teal-700' : 'text-red-600'}`}>{iv.status}: {iv.reason}</span>}
          </div>
          <button className="btn btn-primary mt-2 w-fit" onClick={investigate} disabled={busy}>
            {busy ? 'Investigating…' : '4 · Run multi-agent investigation'}
          </button>
          {error && <p className="text-sm text-red-600">{error}</p>}
        </section>
        <section className="panel">
          <h2 className="font-semibold">Protected identity</h2>
          {ident && (
            <div className="mt-2 text-sm">
              <div>{ident.name}</div>
              <div className="text-[var(--ink2)]">Registered number: {ident.phone}</div>
              <div className="text-[var(--ink2)]">Independent recovery: {ident.recovery_method}</div>
              <div className="mt-3 font-semibold">Trusted contacts</div>
              {ident.trusted_contacts.map((t: any) => (
                <div key={t.name} className="text-[var(--ink2)]">
                  {t.name} ({t.relation}) · {t.phone}
                </div>
              ))}
            </div>
          )}
          {session && (
            <div className="mt-4 rounded-none bg-[var(--panel2)] p-3 text-sm">
              <div className="text-[var(--ink2)]">📧 Code delivered to {ident?.recovery_method} (simulated delivery)</div>
              <div className="mono mt-1 text-2xl tracking-[0.3em]">{session.challenge.nonce_for_trusted_channel}</div>
              <div className="mt-1 text-xs text-[var(--ink2)]">The real relative can read this from their own enrolled channel; an impersonator on a reassigned number cannot.</div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
