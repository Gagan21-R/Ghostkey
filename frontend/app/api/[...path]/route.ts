// Server-side proxy: the browser calls /api/*, this adds the internal token and forwards to FastAPI.
// Neither the GhostKey token nor the DetectifAI key ever reaches the browser.
import { createHash } from 'node:crypto';
import { NextRequest } from 'next/server';

// Same normalisation as the backend: hosting dashboards often add spaces, newlines or quotes to values.
const clean = (v?: string) => (v ?? '').trim().replace(/^['"]+|['"]+$/g, '').trim();
const BACKEND = clean(process.env.BACKEND_URL) || 'http://127.0.0.1:8000';
const TOKEN = clean(process.env.GHOSTKEY_API_TOKEN) || 'ghostkey-dev-token';
console.log(`[ghostkey] proxy internal token fingerprint: ${createHash('sha256').update(TOKEN).digest('hex').slice(0, 8)} -> ${BACKEND}`);

async function forward(req: NextRequest, path: string[]) {
  const url = `${BACKEND}/api/${path.join('/')}${req.nextUrl.search}`;
  const headers: Record<string, string> = { 'X-GhostKey-Token': TOKEN };
  const ct = req.headers.get('content-type');
  if (ct) headers['content-type'] = ct;
  const body = req.method === 'GET' ? undefined : Buffer.from(await req.arrayBuffer());
  try {
    const res = await fetch(url, { method: req.method, headers, body, cache: 'no-store' });
    return new Response(await res.arrayBuffer(), { status: res.status, headers: { 'content-type': res.headers.get('content-type') || 'application/json' } });
  } catch {
    return Response.json({ detail: 'GhostKey backend is not reachable on ' + BACKEND }, { status: 502 });
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
