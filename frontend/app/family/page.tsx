'use client';
import { PAGE_ICON } from '@/lib/icons';
import ModulePage from '@/components/ModulePage';
import FamilyLive from '@/components/live/FamilyLive';

export default function Page() {
  return (
    <ModulePage icon={PAGE_ICON.family} title="Family & SIM impersonation" explain="sim" useCase="family" Live={FamilyLive}
      subtitle="A caller claims to be a relative and asks for money or an OTP — maybe from a reassigned or hijacked number. A familiar number or voice is never enough." />
  );
}
