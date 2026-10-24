// Server-side logger: one JSON line per event to stdout, same fields as the backend
// (ts, level, service, event, request_id). No extra package. Don't use it in browser code.
type Level = 'debug' | 'info' | 'warn' | 'error';

export function log(level: Level, event: string, fields: Record<string, unknown> = {}) {
  const line = JSON.stringify({ ts: new Date().toISOString(), level: level.toUpperCase(), service: 'web', event, ...fields });
  if (level === 'error' || level === 'warn') console.error(line);
  else console.log(line);
}

/** Short random ID sent to FastAPI as X-Request-ID, so one request can be traced across both. */
export function newRequestId() {
  return `web-${Math.random().toString(36).slice(2, 12)}`;
}
