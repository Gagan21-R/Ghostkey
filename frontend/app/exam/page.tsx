'use client';
import { PAGE_ICON } from '@/lib/icons';
import ModulePage from '@/components/ModulePage';
import ExamLive from '@/components/live/ExamLive';

export default function Page() {
  return (
    <ModulePage icon={PAGE_ICON.exam} title="Exam identity verification" explain="face" useCase="exam" Live={ExamLive} liveLabel="Test yourself (webcam)"
      subtitle="Is the person at the camera the student who enrolled? A real face model compares frames with a consented reference. Results go to a proctor — never an automatic cheating verdict." />
  );
}
