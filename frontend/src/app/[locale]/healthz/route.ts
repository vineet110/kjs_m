// Health check for deploy.sh and the Docker HEALTHCHECK (code review CR2).
// Why not "/": the home page has loading.tsx, so Next answers "200 OK" straight away and a page that then
// fails still counts as healthy. This answers 200 only when this Next server can reach the API and the
// database right now. No cache (Next's data cache would keep saying "ok" while the API is down).
// It lives under [locale] because the proxy (next-intl) rewrites /healthz to /en/healthz.
export const dynamic = 'force-dynamic';

const INTERNAL = process.env.API_INTERNAL_URL || 'http://127.0.0.1:8000';

export async function GET() {
  try {
    const r = await fetch(`${INTERNAL}/api/health/ready`, { cache: 'no-store', signal: AbortSignal.timeout(4000) });
    if (r.ok) return new Response('ok', { status: 200, headers: { 'cache-control': 'no-store' } });
    return new Response(`api answered ${r.status}`, { status: 503, headers: { 'cache-control': 'no-store' } });
  } catch {
    return new Response('api unreachable', { status: 503, headers: { 'cache-control': 'no-store' } });
  }
}
