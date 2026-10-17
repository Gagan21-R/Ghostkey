'use client';
import { useRef, useState } from 'react';
import { FlaskConical, Library, Mic, Radar } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { Tabs, Empty } from './ui';
import RegionHero from './RegionHero';
import InvestigationView from './InvestigationView';
import ExamplesGallery from './ExamplesGallery';
import JudgeTest from './JudgeTest';

type T = 'examples' | 'live' | 'judge';

export default function ModulePage({ icon, title, subtitle, explain, useCase, Live, liveLabel = 'Live check' }: {
  icon: LucideIcon; title: string; subtitle: string; explain: string; useCase?: 'exam' | 'family' | 'insurance' | 'banking';
  Live: React.ComponentType<{ onResult: (r: any) => void }>; liveLabel?: string;
}) {
  const [tab, setTab] = useState<T>(useCase ? 'examples' : 'live');
  const [result, setResult] = useState<any>(null);
  const anchor = useRef<HTMLDivElement>(null);
  const show = (r: any) => {
    setResult(r);
    setTimeout(() => anchor.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80);
  };
  return (
    <div>
      <RegionHero region="scenario" icon={icon} title={title} subtitle={subtitle} explain={explain} />
      <div className="mb-5">
        <Tabs<T>
          value={tab}
          onChange={setTab}
          tabs={[
            ...(useCase ? [{ id: 'examples' as T, label: 'Real examples', icon: Library }] : []),
            ...(useCase && useCase !== 'exam' ? [{ id: 'judge' as T, label: 'Test it yourself', icon: Mic }] : []),
            { id: 'live' as T, label: liveLabel, icon: useCase === 'exam' ? Mic : FlaskConical },
          ]}
        />
      </div>
      <div className="fade-in" key={tab}>
        {tab === 'examples' && useCase ? <ExamplesGallery useCase={useCase} onResult={show} /> : tab === 'judge' && useCase && useCase !== 'exam' ? <JudgeTest useCase={useCase} onResult={show} /> : <Live onResult={show} />}
      </div>
      <div ref={anchor} className="scroll-mt-6 pt-8">
        {result ? <InvestigationView rec={result} /> : <Empty icon={Radar} title="No investigation yet" hint="Run an example or a live check — the multi-agent investigation appears here." />}
      </div>
    </div>
  );
}
