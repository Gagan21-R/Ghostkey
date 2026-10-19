// Server-side proxy: the browser calls /api/*, this adds the internal token and forwards to FastAPI.
// Neither the GhostKey token nor the DetectifAI key ever reaches the browser.
import { createHash } from 'node:crypto';
import { NextRequest } from 'next/server';

// Same normalisation as the backend: hosting dashboards often add spaces, newlines or quotes to values.
const clean = (v?: string) => (v ?? '').trim().replace(/^['"]+|['"]+$/g, '').trim();
const BACKEND = clean(process.env.BACKEND_URL) || 'http://127.0.0.1:8000';
const TOKEN = clean(process.env.GHOSTKEY_API_TOKEN) || 'ghostkey-dev-token';
console.log(`[ghostkey] proxy internal token fingerprint: ${createHash('sha256').update(TOKEN).digest('hex').slice(0, 8)} -> ${BACKEND}`);

const RETRIES = 8;              // connection refused right after a deploy: the backend is still starting
const TIMEOUT_MS = 120_000;     // DetectifAI calls can take a while; never hang forever

async function forward(req: NextRequest, path: string[]) {
  const url = `${BACKEND}/api/${path.join('/')}${req.nextUrl.search}`;
  const headers: Record<string, string> = { 'X-GhostKey-Token': TOKEN };
  const ct = req.headers.get('content-type');
  if (ct) headers['content-type'] = ct;
  const admin = req.headers.get('x-admin-token'); // only used by the one-time database import
  if (admin) headers['X-Admin-Token'] = admin;
  const body = req.method === 'GET' || req.method === 'HEAD' ? undefined : Buffer.from(await req.arrayBuffer());
  for (let attempt = 0; ; attempt++) {
    try {
      const res = await fetch(url, { method: req.method, headers, body, cache: 'no-store', signal: AbortSignal.timeout(TIMEOUT_MS) });
      const out: Record<string, string> = { 'content-type': res.headers.get('content-type') || 'application/json' };
      const cd = res.headers.get('content-disposition');
      if (cd) out['content-disposition'] = cd;
      return new Response(await res.arrayBuffer(), { status: res.status, headers: out });
    } catch (e: any) {
      if (e?.name === 'TimeoutError' || e?.name === 'AbortError') {
        return Response.json({ detail: `The GhostKey backend did not answer within ${TIMEOUT_MS / 1000} s. Please retry.` }, { status: 504 });
      }
      // nothing reached the backend (connection refused / reset): safe to retry, the request was never processed
      if (attempt < RETRIES) {
        await new Promise((r) => setTimeout(r, 1000));
        continue;
      }
      return Response.json({ detail: `GhostKey backend is not reachable on ${BACKEND} (it may still be starting — retry in a few seconds)` }, { status: 502 });
    }
  }
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return forward(req, (await ctx.params).path);
}
export async function POST(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return forward(req, (await ctx.params).path);
}
export async function DELETE(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return forward(req, (await ctx.params).path);
}
