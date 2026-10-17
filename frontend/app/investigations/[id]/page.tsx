'use client';
import { use, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import InvestigationView from '@/components/InvestigationView';

export default function InvestigationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [rec, setRec] = useState<any>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    api(`investigations/${id}`).then(setRec).catch((e) => setError(e.message));
  }, [id]);
  if (error) return <p className="text-red-600">{error}</p>;
  return rec ? <InvestigationView rec={rec} /> : <p className="text-[var(--ink2)]">Loading…</p>;
}
