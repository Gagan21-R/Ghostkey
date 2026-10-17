'use client';
import { useEffect, useMemo, useState } from 'react';
import { api, postForm, postJson } from '@/lib/api';
import { ACCEPT_AUDIO } from '@/lib/audio';

export default function InsuranceLive({ onResult }: { onResult: (r: any) => void }) {
  const [data, setData] = useState<any>(null);
  const [claimId, setClaimId] = useState('CLM-2026-1077');
  const [actionType, setActionType] = useState('');
  const [newAccount, setNewAccount] = useState('');
  const [role, setRole] = useState('policyholder');
  const [transcript, setTranscript] = useState('');
  const [audio, setAudio] = useState<File | null>(null);
  const [session, setSession] = useState<any>(null);
  const [code, setCode] = useState('');
  const [challengeCheck, setChallengeCheck] = useState<any>(null);
  const [approval, setApproval] = useState<any>(null);
  const [approvalStatus, setApprovalStatus] = useState('');
  const [result, setResult] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => { api('insurance/claims').then(setData).catch((e) => setError(e.message)); }, []);
  const claim = data?.claims.find((c: any) => c.claim_id === claimId);
  const ph = data?.policyholders.find((p: any) => p.id === claim?.policyholder_id);
  useEffect(() => {
    if (!claim) return;
    setActionType(claim.requested_action);
    setNewAccount(claim.new_payout_account ?? '');
    setRole(claim.claimant_relation === 'self' ? 'policyholder' : 'authorized_representative');
    setSession(null); setChallengeCheck(null); setApproval(null); setApprovalStatus(''); setResult(null); setCode('');
  }, [claimId, data]);  // eslint-disable-line react-hooks/exhaustive-deps

  // the action exactly as the backend will bind it
  const action = useMemo(() => claim && ({ type: actionType, amount: claim.amount, details: { claim_id: claim.claim_id, new_payout_account: newAccount || claim.new_payout_account } }), [claim, actionType, newAccount]);
  const device = 'Policyholder\'s registered phone (simulated)';
  const guard = async (fn: () => Promise<void>) => {
    setBusy(true); setError('');
    try { await fn(); } catch (e: any) { setError(e.message); } finally { setBusy(false); }
  };

  const start = () => guard(async () => { setChallengeCheck(null); setApproval(null); setApprovalStatus(''); setSession(await postJson('sessions', { use_case: 'insurance', identity_id: ph.id, action })); });
  const verifyCode = () => guard(async () => setChallengeCheck(await postJson(`sessions/${session.session_id}/challenge/verify`, { challenge_id: session.challenge.challenge_id, response: code })));
  const requestApproval = () => guard(async () => setApproval(await postJson(`sessions/${session.session_id}/approval`, { action, device })));
  const decide = (ok: boolean) => guard(async () => setApprovalStatus((await postJson(`approvals/${approval.approval_id}/decide`, { approve: ok, device })).status));
  const run = () => guard(async () => {
    const f = new FormData();
    f.append('claim_id', claimId);
    f.append('actor_role', role);
    f.append('transcript', transcript);
    f.append('action_type', actionType);
    if (newAccount) f.append('new_payout_account', newAccount);
    if (challengeCheck) f.append('challenge_check', JSON.stringify(challengeCheck));
    if (approval) f.append('approval_id', approval.approval_id);
    if (audio) f.append('audio', audio);
    onResult(await postForm('insurance/investigate', f));
  });

  return (
    <div className="flex flex-col gap-5">
            <div className="grid gap-4 lg:grid-cols-3">
        <section className="panel lg:col-span-2 flex flex-col gap-3">
          <h2 className="font-semibold">Claims queue (synthetic)</h2>
          <div className="overflow-x-auto">
          <table className="w-full text-sm whitespace-nowrap">
            <thead className="text-left text-xs text-[var(--ink2)]">
              <tr><th>Claim</th><th>Policy</th><th>Type</th><th>Amount</th><th>Incident</th><th>Status</th><th>Request</th></tr>
            </thead>
            <tbody>
              {data?.claims.map((c: any) => {
                const p = data.policyholders.find((x: any) => x.id === c.policyholder_id);
                return (
                  <tr key={c.claim_id} onClick={() => setClaimId(c.claim_id)} className={`cursor-pointer border-t border-[var(--line)] ${c.claim_id === claimId ? 'bg-[var(--panel2)]' : ''}`}>
                    <td className="py-1.5 pr-3 mono">{c.claim_id}</td><td className="pr-3 mono">{p?.policy_ref}</td><td>{c.claim_type}</td>
                    <td>₹{c.amount.toLocaleString('en-IN')}</td><td>{c.incident_date}</td><td>{c.status}</td><td className="text-xs">{c.requested_action}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>
          {claim && ph && (
            <div className="grid gap-3 md:grid-cols-2 text-sm">
              <div className="rounded-none bg-[var(--panel2)] p-3">
                <div className="font-semibold">Policyholder <span className="chip">SYNTHETIC</span></div>
                <div>{ph.name} · {ph.product}</div>
                <div className="text-[var(--ink2)]">Sum insured ₹{ph.sum_insured.toLocaleString('en-IN')} · since {ph.policy_start}</div>
                <div className="text-[var(--ink2)]">Payout account {ph.payout_account}{ph.payout_account_changed_at ? ` (changed ${ph.payout_account_changed_at})` : ''}</div>
                <div className="text-[var(--ink2)]">Representatives: {ph.authorized_representatives.join(', ') || 'none'}</div>
                <div className="text-[var(--ink2)]">Voiceprint: {ph.voice_enrolled ? 'enrolled (demo TTS voice)' : 'none'}</div>
              </div>
              <div className="rounded-none bg-[var(--panel2)] p-3">
                <div className="font-semibold">Claim {claim.claim_id}</div>
                <div>Claimant: {claim.claimant} ({claim.claimant_relation})</div>
                <div className="text-[var(--ink2)]">Reported {claim.reported_date} for incident {claim.incident_date}</div>
                <div className="text-[var(--ink2)]">Documents: {claim.documents.join(', ')}</div>
                <div className="text-[var(--ink2)]">Required: {claim.required_documents.join(', ')}</div>
                {claim.duplicate_of && <div className="text-amber-700">References earlier claim {claim.duplicate_of}</div>}
              </div>
            </div>
          )}
          <h2 className="mt-2 font-semibold">Caller's request</h2>
          <div className="grid gap-3 md:grid-cols-3">
            <label className="label">Action
              <select className="input" value={actionType} onChange={(e) => setActionType(e.target.value)}>
                <option value="submit_claim">Submit claim</option>
                <option value="submit_high_value_claim">Submit high-value claim</option>
                <option value="change_payout_details">Change payout details</option>
              </select>
            </label>
            <label className="label">New payout account (if changing)
              <input className="input" value={newAccount} onChange={(e) => setNewAccount(e.target.value)} />
            </label>
            <label className="label">Caller acts as
              <select className="input" value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="policyholder">policyholder</option>
                <option value="authorized_representative">authorized representative</option>
                <option value="claims_officer">claims officer</option>
              </select>
            </label>
          </div>
          <label className="label">Caller's consented recording (optional — sent to DetectifAI)
            <input type="file" accept={ACCEPT_AUDIO} className="text-xs" onChange={(e) => setAudio(e.target.files?.[0] ?? null)} />
          </label>
          <label className="label">Call notes / transcript
            <textarea className="input" rows={2} value={transcript} onChange={(e) => setTranscript(e.target.value)} />
          </label>
          <h2 className="font-semibold">Independent authentication</h2>
          <div className="flex flex-wrap items-center gap-2">
            <button className="btn" onClick={start} disabled={busy || !ph}>Start verification session</button>
            {session && (<>
              <input className="input w-36" placeholder="code from device" value={code} onChange={(e) => setCode(e.target.value)} />
              <button className="btn" onClick={verifyCode} disabled={busy || !code}>Verify code</button>
              <button className="btn" onClick={requestApproval} disabled={busy}>Send approval to device</button>
            </>)}
          </div>
          {challengeCheck && <span className={`chip w-fit ${challengeCheck.valid ? 'text-teal-700' : 'text-red-600'}`}>challenge: {challengeCheck.reason}</span>}
          {approval && <span className="chip w-fit">approval: {approvalStatus || 'pending'} · bound to {approval.action_hash.slice(0, 10)}…</span>}
          <button className="btn btn-primary w-fit" onClick={run} disabled={busy || !claim}>{busy ? 'Investigating…' : 'Run multi-agent claim review'}</button>
          {error && <p className="text-sm text-red-600">{error}</p>}
        </section>
        <section className="panel">
          <h2 className="font-semibold">📱 Trusted device <span className="chip text-amber-700">SIMULATED</span></h2>
          <p className="text-xs text-[var(--ink2)]">{device}. Not WebAuthn/passkeys.</p>
          {session && (
            <div className="mt-3 rounded-none bg-[var(--panel2)] p-3 text-sm">
              <div className="text-[var(--ink2)]">One-time code (2 min, single use)</div>
              <div className="mono mt-1 text-2xl tracking-[0.3em]">{session.challenge.nonce_for_trusted_channel}</div>
            </div>
          )}
          {approval && (
            <div className="mt-3 rounded-none border-2 border-[var(--ink)] bg-[var(--panel2)] p-3 text-sm">
              <div className="font-semibold">Approve this exact claim action?</div>
              <pre className="mono mt-1 whitespace-pre-wrap">{JSON.stringify(approval.shown_on_device, null, 2)}</pre>
              <div className="mt-2 flex gap-2">
                <button className="btn btn-primary" onClick={() => decide(true)} disabled={busy || !!approvalStatus}>Approve</button>
                <button className="btn" onClick={() => decide(false)} disabled={busy || !!approvalStatus}>Reject</button>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
