'use client';
import { PAGE_ICON } from '@/lib/icons';
import ModulePage from '@/components/ModulePage';
import InsuranceLive from '@/components/live/InsuranceLive';

export default function Page() {
  return (
    <ModulePage icon={PAGE_ICON.insurance} title="Insurance claim verification" explain="insurance" useCase="insurance" Live={InsuranceLive} liveLabel="Claims desk (live)"
      subtitle="A caller submits a claim or asks to change the payout account. Voice, claim data and independent authentication are weighed separately. All records are synthetic." />
  );
}
