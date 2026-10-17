import type { Metadata } from 'next';
import { Space_Grotesk, Space_Mono } from 'next/font/google';
import './globals.css';
import Nav from '@/components/Nav';
import { ChatProvider } from '@/components/Chat';
import Motion from '@/components/Motion';

const display = Space_Grotesk({ subsets: ['latin'], weight: ['400', '500', '600', '700'], variable: '--font-display', display: 'swap' });
const mono = Space_Mono({ subsets: ['latin'], weight: ['400', '700'], variable: '--font-mono', display: 'swap' });

export const metadata: Metadata = { title: 'GHOSTKEY 2.0', description: 'Multi-agent identity defense' };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${mono.variable}`} data-theme="light" suppressHydrationWarning>
      <head>
        {/* apply the saved theme before first paint, so there is no flash of the wrong theme */}
        <script dangerouslySetInnerHTML={{ __html: `try{var t=localStorage.getItem('ghostkey-theme');if(t==='dark'||t==='light')document.documentElement.dataset.theme=t}catch(e){}` }} />
      </head>
      <body className="min-h-screen">
        <Motion>
        <ChatProvider>
          <div className="relative z-10 flex min-h-screen flex-col md:flex-row">
            <Nav />
            <main className="min-w-0 flex-1 p-4 pb-28 md:p-8 md:pb-28">
              <div className="mx-auto max-w-[1300px]">{children}</div>
            </main>
          </div>
        </ChatProvider>
        </Motion>
      </body>
    </html>
  );
}
