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
};

export type Me = { id: number; name: string; email: string; role: 'admin' | 'employee'; permissions: string[] };

export type ApiError = { code: string; message: string; details: Record<string, unknown>; request_id: string | null };

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
    res = await fetch(`${INTERNAL}/api/v1${path}`, { next: { revalidate: REVALIDATE_SECONDS } });
  } catch (err) {
    // During `next build` (e.g. in CI) the API may not be running: build with empty data,
    // the page refreshes itself from the API after REVALIDATE_SECONDS.
    if (IS_BUILD) return null;
    throw err;
  }
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json();
}

// ---------- Browser side (client components): same-origin /api, cookie sent automatically ----------
export class ApiFailure extends Error {
  constructor(public status: number, public body: ApiError) {
    super(body.message);
  }
}

export async function api<T = unknown>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    method: init.method || 'GET',
    headers: {
      'content-type': 'application/json',
      'x-requested-with': 'kjs', // CSRF guard: FastAPI rejects state changes without it
    },
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
    credentials: 'same-origin',
  });
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new ApiFailure(res.status, {
      code: data.code || 'error',
      message: data.message || 'Something went wrong.',
      details: data.details || {},
      request_id: data.request_id || null,
    });
  }
  return data as T;
}
