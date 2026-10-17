'use client';
import { createContext, useContext, useEffect, useRef, useState } from 'react';
import { HelpCircle, MessageCircle, Send, Sparkles, X } from 'lucide-react';
import { answer, TOPICS, topicById } from '@/lib/explain';
import Ghost from './Ghost';

type Msg = { role: 'bot' | 'user'; title?: string; lines: string[] };
type Ctx = { explain: (topic: string, data?: any) => void; open: () => void };
const ChatCtx = createContext<Ctx>({ explain: () => {}, open: () => {} });
export const useExplain = () => useContext(ChatCtx);

const WELCOME: Msg = {
  role: 'bot',
  title: 'Hi, I\'m the GhostKey guide',
  lines: ['Click any **Explain** button on the page and I\'ll tell you what that part means — or ask me a question below.'],
};

export function ChatProvider({ children }: { children: React.ReactNode }) {
  const [isOpen, setOpen] = useState(false);
  // the ghost on the chat button says one word when the chat opens ("hii!") or closes ("boo!")
  const [greet, setGreet] = useState<'' | 'hi' | 'boo'>('');
  const wasOpen = useRef(isOpen);
  useEffect(() => {
    if (wasOpen.current === isOpen) return;
    wasOpen.current = isOpen;
    setGreet(isOpen ? 'hi' : 'boo');
    const t = setTimeout(() => setGreet(''), 1400);
    return () => clearTimeout(t);
  }, [isOpen]);
  const [msgs, setMsgs] = useState<Msg[]>([WELCOME]);
  const [typing, setTyping] = useState(false);
  const [text, setText] = useState('');
  const lastData = useRef<any>(null);
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: 'smooth' });
  }, [msgs, typing]);

  const reply = (m: Msg) => {
    setTyping(true);
    setTimeout(() => {
      setTyping(false);
      setMsgs((x) => [...x, m]);
    }, 450);
  };

  const explain = (topicId: string, data?: any) => {
    const t = topicById(topicId);
    if (!t) return;
    lastData.current = data ?? lastData.current;
    setOpen(true);
    setMsgs((x) => [...x, { role: 'user', lines: [`Explain: ${t.title}`] }]);
    reply({ role: 'bot', title: t.title, lines: t.text(data) });
  };

  const ask = (q: string) => {
    if (!q.trim()) return;
    setMsgs((x) => [...x, { role: 'user', lines: [q] }]);
    const a = answer(q, lastData.current);
    reply({ role: 'bot', title: a.title, lines: a.lines });
    setText('');
  };

  return (
    <ChatCtx.Provider value={{ explain, open: () => setOpen(true) }}>
      {children}
      <div data-chat className="fixed bottom-5 right-5 z-50 flex flex-col items-center">
        {/* the ghost sits on top of the chat button */}
        <div className={`pointer-events-none relative -mb-[7px] transition-transform duration-200 ${greet ? '-translate-y-1.5' : ''}`}>
          {greet && (
            <span role="status" className="absolute -top-8 left-1/2 -translate-x-1/2 whitespace-nowrap border-2 border-[var(--ink)] bg-[var(--panel)] px-1.5 py-0.5 font-mono text-[11px] font-bold uppercase text-[var(--ink)] shadow-[2px_2px_0_0_var(--ink)] fade-in">
              {greet === 'hi' ? 'hii!' : 'boo!'}
            </span>
          )}
          <Ghost size={40} mood={greet || 'idle'} />
        </div>
        <button
          onClick={() => setOpen((o) => !o)}
          className="relative flex h-14 w-14 items-center justify-center border-2 border-[var(--ink)] bg-[var(--hi)] text-[#0b0b0b] shadow-[var(--shadow)] transition-transform hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-0.5 active:translate-y-0.5"
          aria-label={isOpen ? 'Close the GhostKey guide' : 'Open the GhostKey guide'}
          aria-expanded={isOpen}
        >
          {isOpen ? <X size={22} /> : <MessageCircle size={22} />}
        </button>
      </div>
      {isOpen && (
        <div data-chat className="fixed bottom-[10.5rem] right-5 z-50 flex h-[560px] max-h-[calc(100vh-12rem)] w-[380px] max-w-[calc(100vw-40px)] flex-col overflow-hidden rounded-none border-2 border-[var(--ink)] bg-[var(--panel)] shadow-[var(--shadow-lg)] fade-in">
          <div className="flex items-center gap-3 border-b border-[var(--line)] px-4 py-3" style={{ background: 'var(--hi)' }}>
            <div className="flex h-10 w-10 items-center justify-center border-2 border-[var(--ink)] bg-[var(--panel)]">
              <Ghost size={26} mood="hi" />
            </div>
            <div>
              <div className="text-sm font-semibold">GhostKey guide</div>
              <div className="text-[11px] text-[var(--ink2)]">Built-in explainer · works offline</div>
            </div>
          </div>
          <div ref={scroller} className="flex-1 space-y-3 overflow-y-auto p-4">
            {msgs.map((m, i) => (
              <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'} fade-in`}>
                <div className={`max-w-[88%] rounded-none px-3.5 py-2.5 text-[13px] leading-relaxed ${m.role === 'user' ? 'rounded-none bg-[var(--accent)] text-white' : 'rounded-none border-2 border-[var(--ink)] bg-[var(--panel2)]'}`}>
                  {m.title && <div className="mb-1 flex items-center gap-1.5 font-semibold text-blue-700"><Sparkles size={13} />{m.title}</div>}
                  {m.lines.map((l, j) => (
                    <p key={j} className="mb-1.5 last:mb-0" dangerouslySetInnerHTML={{ __html: l.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/\*\*(.+?)\*\*/g, '<b>$1</b>') }} />
                  ))}
                </div>
              </div>
            ))}
            {typing && (
              <div className="flex gap-1 px-2 text-[var(--ink2)]">
                <span className="animate-bounce">•</span><span className="animate-bounce [animation-delay:.15s]">•</span><span className="animate-bounce [animation-delay:.3s]">•</span>
              </div>
            )}
          </div>
          <div className="flex flex-wrap gap-1.5 border-t border-[var(--line)] px-3 pt-2">
            {['overview', 'decision', 'critic', 'sources'].map((id) => (
              <button key={id} className="chip hover:text-[var(--ink)]" onClick={() => explain(id, lastData.current)}>{TOPICS.find((t) => t.id === id)?.title}</button>
            ))}
          </div>
          <form className="flex gap-2 p-3" onSubmit={(e) => { e.preventDefault(); ask(text); }}>
            <input className="input flex-1" placeholder="Ask e.g. why was this held?" value={text} onChange={(e) => setText(e.target.value)} />
            <button className="btn btn-primary px-3" aria-label="Send"><Send size={16} /></button>
          </form>
        </div>
      )}
    </ChatCtx.Provider>
  );
}

export function ExplainButton({ topic, data, label = 'Explain' }: { topic: string; data?: any; label?: string }) {
  const { explain } = useExplain();
  return (
    <button type="button" onClick={() => explain(topic, data)} className="inline-flex items-center gap-1 border-2 border-[var(--ink)] bg-[var(--panel)] px-2.5 py-1 text-[11px] font-bold uppercase text-[var(--ink)] shadow-[var(--shadow-sm)] transition-transform hover:-translate-x-px hover:-translate-y-px hover:bg-[var(--hi)] active:translate-x-0.5 active:translate-y-0.5">
      <HelpCircle size={13} /> {label}
    </button>
  );
}
