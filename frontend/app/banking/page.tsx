'use client';
import { PAGE_ICON } from '@/lib/icons';
import ModulePage from '@/components/ModulePage';
import BankingLive from '@/components/live/BankingLive';

export default function Page() {
  return (
    <ModulePage icon={PAGE_ICON.banking} title="Banking impersonation protection" explain="session" useCase="banking" Live={BankingLive} liveLabel="Live call desk"
      subtitle="A caller asks for a PIN, recovery or payee change. A convincing voice never authorizes it: a one-time code and a device approval bound to the exact change are required." />
  );
}
