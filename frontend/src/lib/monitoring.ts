'use client';
// Laptop monitoring in the portal (backend: app/services/monitoring_service.py).
// One live connection per tab (GET /api/v1/monitoring/stream, Server-Sent Events) for people who may see
// monitoring. The monitoring server pushes to our API the moment an alert, a laptop state or an unlock request
// changes; the API passes a "changed" note down this stream at once, and each part of the page reloads what it
// shows. The note carries no data (each part reloads only what this person may see).
// Pages also reload every `refresh_seconds` (sent by the server on connect), in case a note was missed.
import { useEffect, useRef } from 'react';

export type MonitorState = 'WORKING' | 'BREAK' | 'LOCKED' | 'OFF_DUTY' | 'NO_DEVICE';
export type LiveDevice = { device_id: number; hostname: string; state: MonitorState; online: boolean; last_seen_at: string | null; last_screenshot_at: string | null };
export type LivePerson = { employee_id: string; name: string; department: string | null; status: MonitorState; online: boolean; devices: LiveDevice[] };
export type UnlockRequest = {
  id: number; employee_id: string; name: string; department: string | null; hostname: string;
  closed_at: string; reopened_at: string; working_gap_min: number; reason_code: string; reason_text: string | null;
  requested_at: string; escalated: boolean; decision: 'approved' | 'rejected' | null; decided_at: string | null; comment: string | null;
};
export type MonitorAlert = { id: number; type: string; created_at: string; resolved_at: string | null; employee_id: string | null; name: string | null; data: Record<string, unknown> };
export type DayReport = {
  employee_id: string; name?: string; date?: string; worked_min: number; active_min: number; idle_min: number;
  productive_min: number; neutral_min: number; unproductive_min: number; productive_pct: number | null;
  unaccounted_min: number; lock_count: number; screenshot_count: number;
  top_apps?: { name: string; minutes: number }[]; top_sites?: { name: string; minutes: number }[];
};

/** What changed: `live` (a laptop's state), `unlock` (an unlock request), `alerts`, `bell` (a notification for someone). */
export type Change = 'live' | 'unlock' | 'alerts' | 'bell';

export const MONITOR_PERMS = ['monitoring.view', 'monitoring.approve'];
export const FALLBACK_REFRESH_SECONDS = 60; // until the server says its own value (config/monitoring_link.ini)

type Source = { close(): void; addEventListener(type: string, fn: (e: { data: string }) => void): void };
type Env = { open: (url: string) => Source };

/** The shared connection. Exported for tests; the page uses the hooks below. */
export function createMonitorStream(env: Env, url = '/api/v1/monitoring/stream') {
  const listeners = new Set<(c: Change) => void>();
  let source: Source | null = null;
  let refresh = FALLBACK_REFRESH_SECONDS;

  const start = () => {
    source = env.open(url); // EventSource reconnects by itself after a drop or the server's 30-minute limit
    source.addEventListener('hello', (e) => {
      try { refresh = Number(JSON.parse(e.data).refresh_seconds) || refresh; } catch { /* keep the old value */ }
    });
    source.addEventListener('changed', (e) => {
      let what: Change | null = null;
      try { what = JSON.parse(e.data).what; } catch { return; }
      if (what) listeners.forEach((fn) => fn(what as Change));
    });
  };

  return {
    refreshSeconds: () => refresh,
    subscribe(fn: (c: Change) => void) {
      listeners.add(fn);
      if (listeners.size === 1 && !source) start();
      return () => {
        listeners.delete(fn);
        if (listeners.size === 0 && source) { source.close(); source = null; }
      };
    },
  };
}

let stream: ReturnType<typeof createMonitorStream> | null = null;
function theStream() {
  if (!stream) stream = createMonitorStream({ open: (u) => new EventSource(u, { withCredentials: true }) });
  return stream;
}

/** Runs `onChange` the moment one of `kinds` changes, and every refresh_seconds anyway. `enabled` = false
 *  (no permission, area off) opens no connection. */
export function useMonitorChanges(kinds: Change[], onChange: () => void, enabled = true) {
  const fn = useRef(onChange);
  fn.current = onChange;
  const key = kinds.join(',');
  useEffect(() => {
    if (!enabled) return;
    const s = theStream();
    const want = new Set(key.split(','));
    const off = s.subscribe((c) => { if (want.has(c)) fn.current(); });
    let timer = 0;
    const again = () => { timer = window.setTimeout(() => { if (document.visibilityState === 'visible') fn.current(); again(); }, s.refreshSeconds() * 1000); };
    again();
    return () => { off(); window.clearTimeout(timer); };
  }, [key, enabled]);
}

export function stateLabel(s: MonitorState | string): string {
  return ({ WORKING: 'Working', BREAK: 'On a break', LOCKED: 'Locked', OFF_DUTY: 'Off duty', NO_DEVICE: 'No laptop' } as Record<string, string>)[s] ?? s;
}

export function minutes(m: number | null | undefined): string {
  const v = Math.max(0, Math.round(m ?? 0));
  return v >= 60 ? `${Math.floor(v / 60)} h ${v % 60} min` : `${v} min`;
}
