// Types mirror the FastAPI schemas. TODO (Phase 1 checklist): generate these from OpenAPI
// instead of writing them by hand.

export type Category = { id: number; slug: string; name: string; description: string; product_count: number };

export type Product = {
  id: number; slug: string; name: string; description: string; pack_formats: string; moq: string;
  image_path: string; private_label: boolean; is_best_seller: boolean; category_slug: string; category_name: string;
};

export type Lead = {
  id: number; source: string; name: string; company: string; email: string; phone: string; country: string;
  buyer_type: string; quantity: string; message: string; chat_summary: string; source_page: string;
  status: 'new' | 'contacted' | 'closed'; product_name: string | null; category_name: string | null; created_at: string;
  assigned_to: number | null; owner_name: string | null; responded_at: string | null; resolved_at: string | null;
  outcome: string; note_count: number; sla_state: 'ok' | 'due_soon' | 'overdue' | 'done'; sla_label: string;
};
export type LeadNote = { id: number; kind: string; text: string; user_name: string; created_at: string };
export type Colleague = { id: number; name: string };
export type Notice = { id: number; kind: string; title: string; body: string; link: string; read: boolean; created_at: string };

export type Me = { id: number; name: string; email: string; role: 'admin' | 'employee'; permissions: string[] };

export type ApiError = { code: string; message: string; details: Record<string, unknown>; request_id: string | null };

import { log, newRequestId } from './logger';

// ---------- Server side (server components): talk to FastAPI directly ----------
const INTERNAL = process.env.API_INTERNAL_URL || 'http://127.0.0.1:8000';

// Public pages reuse API answers for 60 s instead of asking the database on every visit.
// (Our DB is far away, so each uncached page costs seconds.) Admin changes show within a minute;
// on-demand revalidation (Phase 2) will make that instant.
const REVALIDATE_SECONDS = 60;
const IS_BUILD = process.env.NEXT_PHASE === 'phase-production-build';

/** For public pages. Returns null on 404 so the page can call notFound(). */
export async function serverGet<T>(path: string): Promise<T | null> {
  let res: Response;
  try {
    // No X-Request-ID header here: Next.js caches by URL + headers, and a new ID every time
    // would turn the cache off. We log the ID FastAPI gives back instead.
    res = await fetch(`${INTERNAL}/api/v1${path}`, { next: { revalidate: REVALIDATE_SECONDS } });
  } catch (err) {
    // During `next build` (e.g. in CI) the API may not be running: build with empty data,
    // the page refreshes itself from the API after REVALIDATE_SECONDS.
    if (IS_BUILD) return null;
    log('error', 'api.unreachable', { path });
    throw err;
  }
  if (res.status === 404) return null;
  if (!res.ok) {
    const requestId = res.headers.get('x-request-id');
    log('error', 'api.failed', { path, status: res.status, request_id: requestId });
    throw new Error(`API ${path} failed: ${res.status} (request ${requestId})`);
  }
  return res.json();
}

// ---------- Browser side (client components): same-origin /api, cookie sent automatically ----------
export class ApiFailure extends Error {
  constructor(public status: number, public body: ApiError) {
    super(body.message);
  }
}

/** Turns an answer into the data or an ApiFailure (shared by api() and upload()). The answer must be
 *  readable JSON. Not readable: fine for an error (e.g. a proxy's HTML error page; the status is still
 *  reported), but a "success" we can't read (HTML from a proxy, a connection cut while reading) is an
 *  error, never an empty `{}` passed off as the data. Error code for support: the server's, else ours
 *  (the server logs the X-Request-ID we send, so both lead to the same log lines). */
async function readAnswer<T>(res: Response, requestId: string, signal: AbortSignal | undefined, fallback: string): Promise<T> {
  if (res.status === 204) return undefined as T;
  let data;
  try {
    data = await res.json();
  } catch (err) {
    if (signal?.aborted) throw err; // the time limit ran out while reading: a time-out (see api())
    if (res.ok)
      throw new ApiFailure(res.status, { code: 'bad_response', message: 'The server sent an answer that could not be read.', details: {}, request_id: requestId });
    data = {};
  }
  if (!res.ok) {
    throw new ApiFailure(res.status, {
      code: data.code || 'error',
      message: data.message || fallback,
      details: data.details || {},
      request_id: data.request_id || requestId,
    });
  }
  return data as T;
}

/** timeoutMs (optional): give up after this long, so a server that takes the request but never answers
 *  ends as an error (ApiFailure, status 0, code "timeout") instead of a wait with no end. */
export async function api<T = unknown>(
  path: string,
  init: { method?: string; body?: unknown; timeoutMs?: number } = {},
): Promise<T> {
  const requestId = newRequestId(); // shows up on every backend log line for this click
  const signal = init.timeoutMs ? AbortSignal.timeout(init.timeoutMs) : undefined;
  try {
    const res = await fetch(`/api/v1${path}`, {
      method: init.method || 'GET',
      headers: {
        'content-type': 'application/json',
        'x-requested-with': 'kjs', // CSRF guard: FastAPI rejects state changes without it
        'x-request-id': requestId,
      },
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
      credentials: 'same-origin',
      signal,
    });
    return await readAnswer<T>(res, requestId, signal, 'Something went wrong.');
  } catch (err) {
    if (signal?.aborted)
      throw new ApiFailure(0, { code: 'timeout', message: 'The server took too long to answer.', details: {}, request_id: requestId });
    throw err;
  }
}

// ---------- Attendance ----------
export type Today = {
  day: string; check_in: string | null; check_out: string | null; status: string | null;
  hours: number; shift: string; is_available: boolean;
};
export type WeekDay = { day: string; state: string; check_in: string | null; check_out: string | null; hours: number; working_day: boolean };
export type Week = { week_start: string; days: WeekDay[]; summary: Record<string, number>; total_hours: number };
export type Regularization = {
  id: number; user_id: number; user_name: string; day: string; check_in: string; check_out: string | null;
  reason: string; status: 'pending' | 'approved' | 'rejected'; created_at: string;
};
export type Holiday = { id: number; day: string; name: string };

/** Multipart upload (files). Same CSRF header and answer rules as api(); the browser sets the content type.
 *  No time limit: a big file on a slow line may take long. */
export async function upload<T = unknown>(path: string, form: FormData): Promise<T> {
  const requestId = newRequestId();
  const res = await fetch(`/api/v1${path}`, {
    method: 'POST', body: form, credentials: 'same-origin',
    headers: { 'x-requested-with': 'kjs', 'x-request-id': requestId },
  });
  return readAnswer<T>(res, requestId, undefined, 'Upload failed.');
}

export type StoredFile = {
  id: number; name: string; content_type: string; size: number; owner_type: string; owner_id: string;
  is_public: boolean; uploaded_by_name: string; created_at: string; delete_status: string; delete_reason: string;
  requested_by_name?: string;
};

// ---------- Order boards ----------
export type BoardStep = {
  id: number; position: number; name: string; percent: number | null; days: number | null;
  planned_start: string; planned_end: string; status: 'pending' | 'active' | 'done'; started_at: string | null; done_at: string | null;
  used_pct: number; task_templates: string[]; checklist: { text: string; done: boolean }[]; members: Colleague[];
};
export type BoardSummary = {
  code: string; name: string; client: string; priority: string; start: string; deadline: string; split_mode: string;
  status: string; final_status: string | null; notes: string; state: 'on_track' | 'at_risk' | 'late_board' | 'finished';
  steps_done: number; steps_total: number; current_step: string | null; current_used_pct: number | null;
};
export type Board = BoardSummary & { steps: BoardStep[]; my_step_ids: number[]; can_manage: boolean };

// ---------- Public content ----------
export type PublicConfig = {
  site_name: string;
  features: { koko: boolean; offers_ticker: boolean; configurator: boolean; partners: boolean; gated_actions: boolean; whatsapp_button: boolean };
};
export type Offer = { id: number; text: string; link: string };
export type Texts = Record<string, string>;
export type PublicFile = { id: number; name: string; content_type: string; url: string };

/** Feature switches from config/features.ini. If the API is down, assume the safe defaults. */
export async function features(): Promise<PublicConfig['features']> {
  const c = await serverGet<PublicConfig>('/public/config').catch(() => null);
  return c?.features ?? { koko: true, offers_ticker: false, configurator: false, partners: true, gated_actions: true, whatsapp_button: true };
}

/** Editable website text (Admin > Website). Falls back to the given text if the API is down. */
export async function texts(): Promise<Texts> {
  return (await serverGet<Texts>('/public/texts').catch(() => null)) ?? {};
}

// ---------- Auto-assign ----------
export type BuyerRecord = {
  id: number; category: string; company: string; contact_name: string; email: string; phone: string;
  country: string; website: string; notes: string; status: 'assigned' | 'done' | 'skipped' | 'new'; outcome: string; done_at: string | null;
};
export type BatchInfo = { id: number; day: string; status: 'open' | 'done'; size: number; done: number; records: BuyerRecord[] };

// ---------- Tasks ----------
export type Task = {
  id: number; title: string; notes: string; due_at: string | null; status: 'todo' | 'doing' | 'done'; outcome: string;
  source: string; source_ref: string; assignee_id: number; assignee_name: string; created_by_name: string;
  overdue: boolean; completed_at: string | null; created_at: string;
};
export type TaskStats = { total: number; done: number; pending: number; overdue: number };
