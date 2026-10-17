import { api } from './api';

/**
 * Frontend integration smoke test: exercises the browser → Next.js proxy → FastAPI path for the main screens
 * (no DetectifAI credits) and stores the result as a persistent report via /api/reports/ingest.
 */
const CHECKS: [string, string, (b: any) => boolean][] = [
  ['GET /api/health (no token)', 'health', (b) => b.ok === true],
  ['GET /api/provider/status (proxy adds token)', 'provider/status', (b) => b.key_configured === true && !('api_key' in b)],
  ['GET /api/identities', 'identities', (b) => Array.isArray(b)],
  ['GET /api/examples/family', 'examples/family', (b) => b.examples?.length >= 10],
  ['GET /api/examples/exam', 'examples/exam', (b) => b.cases?.length >= 10 || b.examples?.length >= 10],
  ['GET /api/scenarios', 'scenarios', (b) => Array.isArray(b) && b.length >= 17],
  ['GET /api/reports/stats', 'reports/stats', (b) => typeof b.total === 'number'],
  ['GET /api/local/downloads', 'local/downloads', (b) => 'files' in b],
];

export async function runFrontendSmoke(): Promise<{ report_id: string }> {
  const steps: { name: string; status: string; detail: string }[] = [];
  for (const [name, path, ok] of CHECKS) {
    const t = performance.now();
    try {
      const body = await api(path);
      const pass = ok(body);
      steps.push({ name, status: pass ? 'completed' : 'failed', detail: `${pass ? 'response shape OK' : 'unexpected response shape'} · ${Math.round(performance.now() - t)} ms` });
    } catch (e: any) {
      steps.push({ name, status: 'failed', detail: e.message });
    }
  }
  // the proxy must never leak the internal token to the browser
  const leaked = document.documentElement.innerHTML.includes('ghostkey-dev-token');
  steps.push({ name: 'internal token not present in the page', status: leaked ? 'failed' : 'completed', detail: leaked ? 'token found in page HTML' : 'not found' });
  const failed = steps.filter((s) => s.status !== 'completed');
  return api('reports/ingest', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      category: 'frontend_integration', name: 'Frontend integration smoke test', endpoint: `browser ${location.origin}`, provider: 'none',
      status: failed.length ? 'FAIL' : 'PASS', summary: `${steps.length - failed.length}/${steps.length} browser → proxy → API checks passed`,
      steps, expected: { description: 'every screen API responds through the Next.js proxy with the expected shape' },
      acceptance: steps.map((s) => ({ criterion: s.name, satisfied: s.status === 'completed', actual: s.detail })),
    }),
  });
}
