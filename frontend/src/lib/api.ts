// Types mirror the FastAPI schemas. TODO (Phase 1 checklist): generate these from OpenAPI
// instead of writing them by hand.

export type Category = { id: number; slug: string; name: string; description: string; product_count: number };

export type Product = {
  id: number; slug: string; name: string; description: string; pack_formats: string; moq: string;
  image_path: string; private_label: boolean; is_best_seller: boolean; category_slug: string; category_name: string;
  offer_percent: number | null; // "Up to X% OFF" badge; null = no offer
};

export type Lead = {
  extra?: Record<string, string>; // "Extra Info": file columns we have no field for, kept by choice
  id: number; source: string; name: string; company: string; email: string; phone: string; country: string;
  buyer_type: string; quantity: string; message: string; chat_summary: string; source_page: string;
  status: 'new' | 'contacted' | 'closed'; product_name: string | null; category_name: string | null; created_at: string;
  assigned_to: number | null; owner_name: string | null; responded_at: string | null; resolved_at: string | null;
  outcome: string; note_count: number; sla_state: 'ok' | 'due_soon' | 'overdue' | 'done'; sla_label: string;
  updated_at: string | null; created_by_name: string | null;
};
/** One person who sent enquiries (Lead Management > Contacts). `lead_id` = their newest enquiry. */
export type Contact = { lead_id: number; name: string; email: string; phone: string; active: number; inactive: number; total: number; last_at: string };
export type ContactDetail = { lead: Lead; enquiries: Lead[] };
/** A staff account, as the admin sees it (Users page, User Creation Form). */
export type StaffUser = {
  id: number; name: string; email: string; phone: string | null; role: 'admin' | 'employee'; status: string;
  permissions: string[]; created_at: string; employee_code: string; branch: string; reporting_to: number | null;
};
export type LeadNote = { id: number; kind: string; text: string; user_name: string; created_at: string };
export type Colleague = { id: number; name: string };
export type Notice = { id: number; kind: string; title: string; body: string; link: string; read: boolean; created_at: string };

/** `modules`: portal area -> can this person use it (config/modules.ini, see lib/modules.ts). */
export type Me = { id: number; name: string; email: string; role: 'admin' | 'employee'; permissions: string[]; modules?: Record<string, boolean> };

export type ApiError = { code: string; message: string; details: Record<string, unknown>; request_id: string | null };

import { cache } from 'react';
import { log, newRequestId } from './logger';
import { moduleOff } from './modules';

// ---------- Server side (server components): talk to FastAPI directly ----------
const INTERNAL = process.env.API_INTERNAL_URL || 'http://127.0.0.1:8000';

// Public pages reuse API answers for 60 s instead of asking the database on every visit.
// (Our DB is far away, so each uncached page costs seconds.) Admin changes show within a minute;
// on-demand revalidation (Phase 2) will make that instant.
const REVALIDATE_SECONDS = 60;
const IS_BUILD = process.env.NEXT_PHASE === 'phase-production-build';
// A slow database must not keep a buyer waiting until nginx gives up (CR4): stop after this, and the
// page's error.tsx shows "Try again" with our phone number.
const SERVER_TIMEOUT_MS = 15_000;

/** For public pages. Returns null on 404 so the page can call notFound().
 *  Wrapped in React cache(): the time limit (a `signal`) turns off Next's sharing of identical fetches,
 *  and cache() brings it back, so the layout, generateMetadata and the page asking for the same path
 *  during one request cost one API call, not three. */
export const serverGet = cache(async function serverGet<T>(path: string): Promise<T | null> {
  let res: Response;
  try {
    // No X-Request-ID header here: Next.js caches by URL + headers, and a new ID every time
    // would turn the cache off. We log the ID FastAPI gives back instead.
    res = await fetch(`${INTERNAL}/api/v1${path}`, {
      next: { revalidate: REVALIDATE_SECONDS },
      signal: AbortSignal.timeout(SERVER_TIMEOUT_MS),
    });
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
});

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
    if (res.status === 404 && data.code === 'module_off') moduleOff(); // the portal frame shows "Not available yet"
    throw new ApiFailure(res.status, {
      code: data.code || 'error',
      message: data.message || fallback,
      details: data.details || {},
      request_id: data.request_id || requestId,
    });
  }
  return data as T;
}

/** Every call has a time limit (R40), so a server that takes the request but never answers ends as an error
 *  instead of a wait with no end, and no caller has to remember it:
 *  - reads (GET, or safeToRepeat) give up after READ_TIMEOUT_MS: ApiFailure, status 0, code "timeout";
 *  - saves (POST / PUT / PATCH / DELETE) wait SAVE_TIMEOUT_MS, longer than nginx's 60 s, so the server's
 *    own answer (or nginx's 504) normally comes first.
 *  A save that ends without a clear answer (time-out, network cut, 502 / 504, an unreadable "OK") may still
 *  have been saved by the server. Saying "failed" would make people click again and save it twice (a second
 *  user, a second punch), so it ends as code "unconfirmed" with a "refresh to check" message instead.
 *  timeoutMs: a different limit for one call. safeToRepeat: a POST that only reads or is harmless to repeat
 *  (a preview, log in): treated as a read. Uploads use upload(), which has no limit. */
export const READ_TIMEOUT_MS = 20_000;
export const SAVE_TIMEOUT_MS = 90_000;
const UNCONFIRMED = "The server didn't confirm. It may have been saved: refresh to check before trying again.";
export async function api<T = unknown>(
  path: string,
  init: { method?: string; body?: unknown; timeoutMs?: number; safeToRepeat?: boolean } = {},
): Promise<T> {
  const requestId = newRequestId(); // shows up on every backend log line for this click
  const method = init.method || 'GET';
  const isSave = method !== 'GET' && !init.safeToRepeat;
  const signal = AbortSignal.timeout(init.timeoutMs ?? (isSave ? SAVE_TIMEOUT_MS : READ_TIMEOUT_MS));
  try {
    const res = await fetch(`/api/v1${path}`, {
      method,
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
    if (isSave && unclear(err, signal))
      throw new ApiFailure(0, { code: 'unconfirmed', message: UNCONFIRMED, details: {}, request_id: requestId });
    if (signal.aborted)
      throw new ApiFailure(0, { code: 'timeout', message: 'The server took too long to answer.', details: {}, request_id: requestId });
    throw err;
  }
}

/** Did this request end without a clear yes or no from our server? */
function unclear(err: unknown, signal: AbortSignal) {
  if (signal.aborted || !(err instanceof ApiFailure)) return true; // time-out, or the network failed
  return err.status === 502 || err.status === 504 || err.body.code === 'bad_response'; // nginx gave up, or an unreadable answer
}

// ---------- Attendance ----------
export type PunchItem = { id?: number; type: string; time: string; notes?: string | null; at?: string };
export type Today = {
  day: string; check_in: string | null; check_out: string | null; status: string | null;
  hours: number; shift: string; shift_name?: string; shift_code?: string; is_available: boolean;
  is_checked_in?: boolean; punches?: PunchItem[];
};
export type WeekDay = {
  day: string; state: string; check_in: string | null; check_out: string | null;
  hours: number; working_day: boolean; is_checked_in?: boolean; punches?: PunchItem[];
};
export type Week = { week_start: string; days: WeekDay[]; summary: Record<string, number>; total_hours: number };
export type Regularization = {
  id: number; user_id: number; user_name: string; day: string; check_in: string; check_out: string | null;
  reason: string; status: 'pending' | 'approved' | 'rejected'; created_at: string;
};
export type Holiday = { id: number; day: string; name: string };

export type Shift = {
  id: number; name: string; code: string; start_time: string; end_time: string; is_night_shift: boolean; is_active?: boolean;
};

export type MonthDay = {
  day: string; day_num: number; weekday: number; state: string;
  check_in: string | null; check_out: string | null; hours: number; working_day: boolean; source: string | null;
};

export type MonthView = {
  year: number; month: number; month_name: string; user_id: number; user_name: string;
  shift: { name: string; code: string; hours: string };
  days: MonthDay[]; summary: Record<string, number>; total_hours: number; working_days: number;
};

export type LeaveRequest = {
  id: number; user_id: number; user_name: string; leave_type: string;
  start_date: string; end_date: string; is_half_day: boolean; half_day_session: string | null;
  reason: string; status: 'pending' | 'approved' | 'rejected' | 'cancelled'; working_days: number;
  decided_by?: number; decided_at?: string; rejection_reason?: string; created_at?: string;
};

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
  own_request?: boolean; // I asked for this delete: someone else decides it
};

// ---------- Order boards ----------
export type BoardStep = {
  id: number; position: number; name: string; percent: number | null; days: number | null;
  planned_start: string; planned_end: string; status: 'pending' | 'active' | 'done'; started_at: string | null; done_at: string | null;
  used_pct: number; task_templates: string[]; checklist: { text: string; done: boolean }[];
  members: (Colleague & { is_head: boolean })[]; // the step's people; heads first
};
/** One line of a board's History tab (read from the audit log, which nobody can edit). */
export type BoardHistoryItem = { id: number; at: string; who: string; action: string; text: string };
export type BoardHistory = { items: BoardHistoryItem[]; more: boolean };
/** Someone on a board: the owner first, then by name. `steps` = positions of the steps they work on. */
export type BoardPerson = Colleague & { is_owner: boolean; steps: number[] };
export type BoardSummary = {
  code: string; name: string; client: string; priority: string; start: string; deadline: string; split_mode: string;
  status: string; final_status: string | null; notes: string; state: 'on_track' | 'at_risk' | 'late_board' | 'finished';
  steps_done: number; steps_total: number; current_step: string | null; current_used_pct: number | null;
};
export type Board = BoardSummary & {
  steps: BoardStep[]; my_step_ids: number[]; can_manage: boolean;
  owner: { id: number | null; name: string }; people: BoardPerson[];
  can_edit: boolean; // owner or boards.manage: people, step people, finishing
  can_decide_deletes: boolean; // may approve / reject file delete requests on this board
  plan_locked: boolean; // the owner locked the plan: only the owner (or boards.manage) changes it
  can_edit_plan: boolean; // this person may change dates, sizes and steps now
  plan_version: string; // fingerprint of the plan; the editor sends it back so a newer change isn't undone
};

// ---------- Public content ----------
export type PublicConfig = {
  site_name: string;
  features: { koko: boolean; offers_ticker: boolean; configurator: boolean; partners: boolean; gated_actions: boolean; whatsapp_button: boolean; connect_popup?: boolean };
};
export type Offer = { id: number; text: string; link: string };
/** Koko's catalogue card: on the first reply on a product or category page (from the database, not the AI). */
export type KokoCatalogue = {
  category_name: string; category_slug: string;
  products: { name: string; slug: string; image_path: string }[];
};
export type KokoReply = { reply: string; suggest_enquiry: boolean; catalogue?: KokoCatalogue | null };
export type Texts = Record<string, string>;
export type PublicFile = { id: number; name: string; content_type: string; url: string };

/** Feature switches from config/features.ini. If the API is down, assume the safe defaults. */
export async function features(): Promise<PublicConfig['features']> {
  const c = await serverGet<PublicConfig>('/public/config').catch(() => null);
  return c?.features ?? { koko: true, offers_ticker: false, configurator: false, partners: true, gated_actions: true, whatsapp_button: true, connect_popup: true };
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
