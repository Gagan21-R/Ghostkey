'use client';
import { useEffect, useMemo, useState } from 'react';
import { api, postForm, postJson } from '@/lib/api';
import { ACCEPT_AUDIO } from '@/lib/audio';

const ACTIONS = [
  ['pin_change', 'Change PIN'],
  ['recovery_change', 'Change recovery email/phone'],
  ['account_detail_change', 'Change account details'],
  ['add_payee', 'Add payee'],
  ['large_transfer', 'Large transfer'],
  ['balance_enquiry', 'Balance enquiry (non-sensitive)'],
];

export default function BankingLive({ onResult }: { onResult: (r: any) => void }) {
  const [ids, setIds] = useState<any[]>([]);
  const [identityId, setIdentityId] = useState('id-zira');
  const [actionType, setActionType] = useState('pin_change');
  const [amount, setAmount] = useState('');
  const [payee, setPayee] = useState('');
  const [role, setRole] = useState('customer');
  const [transcript, setTranscript] = useState("Hi, it's Zira. I forgot my PIN, please reset it now.");
  const [audio, setAudio] = useState<File | null>(null);
  const [session, setSession] = useState<any>(null);
  const [code, setCode] = useState('');
  const [challengeCheck, setChallengeCheck] = useState<any>(null);
  const [approval, setApproval] = useState<any>(null);
  const [approvalStatus, setApprovalStatus] = useState('');
  const [result, setResult] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api('identities').then((l) => setIds(l.filter((i: any) => i.use_case === 'banking')));
  }, []);
  const ident = ids.find((i) => i.id === identityId);
  const action = useMemo(() => ({ type: actionType, amount: amount ? Number(amount) : null, details: payee ? { payee } : {} }), [actionType, amount, payee]);

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

  const startSession = () =>
    guard(async () => {
      setChallengeCheck(null);
      setApproval(null);
      setApprovalStatus('');
      setResult(null);
      setSession(await postJson('sessions', { use_case: 'banking', identity_id: identityId, action }));
    });
  const verifyCode = () => guard(async () => setChallengeCheck(await postJson(`sessions/${session.session_id}/challenge/verify`, { challenge_id: session.challenge.challenge_id, response: code })));
  const requestApproval = () => guard(async () => setApproval(await postJson(`sessions/${session.session_id}/approval`, { action, device: ident?.trusted_device })));
  const decide = (approve: boolean) =>
    guard(async () => {
      const r = await postJson(`approvals/${approval.approval_id}/decide`, { approve, device: ident?.trusted_device });
      setApprovalStatus(r.status ?? r.reason);
    });
  const investigate = () =>
    guard(async () => {
      const f = new FormData();
      f.append('use_case', 'banking');
      f.append('identity_id', identityId);
      f.append('action', JSON.stringify(action));
      f.append('actor_role', role);
      f.append('transcript', transcript);
      if (challengeCheck) f.append('challenge_check', JSON.stringify(challengeCheck));
      if (approval) f.append('approval_id', approval.approval_id);
      if (audio) f.append('audio', audio);
      onResult(await postForm('investigate', f));
    });

  return (
    <div className="flex flex-col gap-5">
            <div className="grid gap-4 lg:grid-cols-3">
        <section className="panel flex flex-col gap-3 lg:col-span-2">
          <h2 className="font-semibold">1 · Incoming call & requested change</h2>
          <div className="grid gap-3 md:grid-cols-3">
            <label className="label">
              Claimed customer
              <select className="input" value={identityId} onChange={(e) => setIdentityId(e.target.value)}>
                {ids.map((i) => (
                  <option key={i.id} value={i.id}>
                    {i.name} {i.speaker_enrolled ? '· voiceprint' : ''}
                  </option>
                ))}
              </select>
            </label>
            <label className="label">
              Requested action
              <select className="input" value={actionType} onChange={(e) => setActionType(e.target.value)}>
                {ACTIONS.map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </select>
            </label>
            <label className="label">
              Who is performing it
              <select className="input" value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="customer">customer (self-service)</option>
                <option value="support_agent">support agent</option>
              </select>
            </label>
            <label className="label">
              Amount (₹, optional)
              <input className="input" value={amount} onChange={(e) => setAmount(e.target.value)} />
            </label>
            <label className="label">
              Payee / detail (optional)
              <input className="input" value={payee} onChange={(e) => setPayee(e.target.value)} />
            </label>
            <label className="label">
              Caller audio (WAV/MP3/OGG, 4–60 s)
              <input type="file" accept={ACCEPT_AUDIO} className="text-xs" onChange={(e) => setAudio(e.target.files?.[0] ?? null)} />
            </label>
          </div>
          <label className="label">
            Call transcript
            <textarea className="input" rows={2} value={transcript} onChange={(e) => setTranscript(e.target.value)} />
          </label>
          <p className="text-xs text-[var(--ink2)]">
            Audio is sent to DetectifAI (speaker verification + deepfake check if the customer has a voiceprint, otherwise the deepfake check). Each check costs credits.
          </p>

          <h2 className="mt-2 font-semibold">2 · Independent authentication</h2>
          <div className="flex flex-wrap items-center gap-2">
            <button className="btn" onClick={startSession} disabled={busy}>
              Start verification session
            </button>
            {session && (
              <>
                <input className="input w-36" placeholder="code from device" value={code} onChange={(e) => setCode(e.target.value)} />
                <button className="btn" onClick={verifyCode} disabled={busy || !code}>
                  Verify code
                </button>
                <button className="btn" onClick={requestApproval} disabled={busy}>
                  Send approval to trusted device
                </button>
              </>
            )}
          </div>
          {challengeCheck && (
            <span className={`chip w-fit ${challengeCheck.valid ? 'text-teal-700' : 'text-red-600'}`}>challenge: {challengeCheck.reason}</span>
          )}
          {approval && <span className="chip w-fit">approval: {approvalStatus || 'pending on device'} · bound to action hash {approval.action_hash.slice(0, 10)}…</span>}
          <p className="text-xs text-[var(--ink2)]">Tip: approve, then change the action or amount before running — the earlier approval becomes invalid (rule 8). Verify the same code twice to see a replay rejection.</p>

          <button className="btn btn-primary mt-2 w-fit" onClick={investigate} disabled={busy}>
            {busy ? 'Investigating…' : '3 · Run multi-agent investigation'}
          </button>
          {error && <p className="text-sm text-red-600">{error}</p>}
        </section>

        <section className="panel border-sky-800/60">
          <h2 className="font-semibold">📱 Trusted device (simulated)</h2>
          <p className="text-xs text-[var(--ink2)]">{ident?.trusted_device || '—'}</p>
          {!session && <p className="mt-3 text-sm text-[var(--ink2)]">Start a session to deliver a one-time code here.</p>}
          {session && (
            <div className="mt-3 rounded-none bg-[var(--panel2)] p-3 text-sm">
              <div className="text-[var(--ink2)]">One-time verification code (expires in 2 min, single use)</div>
              <div className="mono mt-1 text-2xl tracking-[0.3em] text-[var(--ink)]">{session.challenge.nonce_for_trusted_channel}</div>
              <div className="mt-1 text-xs text-[var(--ink2)]">Shown only on the enrolled device — never read out to the caller.</div>
            </div>
          )}
          {approval && (
            <div className="mt-3 rounded-none border-2 border-[var(--ink)] bg-[var(--panel2)] p-3 text-sm">
              <div className="font-semibold">Approve this exact change?</div>
              <pre className="mono mt-1 whitespace-pre-wrap">{JSON.stringify(approval.shown_on_device, null, 2)}</pre>
              <div className="mt-2 flex gap-2">
                <button className="btn btn-primary" onClick={() => decide(true)} disabled={busy || !!approvalStatus}>
                  Approve
                </button>
                <button className="btn" onClick={() => decide(false)} disabled={busy || !!approvalStatus}>
                  Reject
                </button>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
