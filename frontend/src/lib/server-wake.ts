// The API sleeps when nobody has used it for a while (Render's free plan: about 15 minutes) and takes up to
// a couple of minutes to wake. While it wakes, Render answers every call with its own "Application loading"
// HTML page and status 503, never our JSON. A login sent then failed with "Something went wrong" (or timed
// out after 20 s). So the login page wakes the server as soon as it opens, and waits for it before logging in.
//
// /api/health is our cheapest route (no database): JSON {"status":"ok"} only when OUR app answers.

export const WAKE_LIMIT_MS = 120_000; // the longest we wait for the server to wake
const STEP_MS = 3_000; // ask again this often while it wakes
const ASK_TIMEOUT_MS = 8_000; // one question may take this long (a waking server can hold the request)

/** Is our API answering right now? Render's loading page (503, HTML) or no answer = no. */
export async function serverAwake(timeoutMs = ASK_TIMEOUT_MS): Promise<boolean> {
  try {
    const res = await fetch('/api/health', { cache: 'no-store', signal: AbortSignal.timeout(timeoutMs) });
    if (!res.ok) return false;
    const data = await res.json();
    return data?.status === 'ok';
  } catch {
    return false;
  }
}

/** Waits until the API answers, at most limitMs. `onWaiting` runs once, when the first ask finds it asleep
 *  (to tell the person why it takes long). Returns false if it still isn't awake in time. */
export async function waitForServer(opts: { limitMs?: number; stepMs?: number; askMs?: number; onWaiting?: () => void } = {}): Promise<boolean> {
  const { limitMs = WAKE_LIMIT_MS, stepMs = STEP_MS, askMs = ASK_TIMEOUT_MS, onWaiting } = opts;
  const end = Date.now() + limitMs;
  let told = false;
  for (;;) {
    if (await serverAwake(askMs)) return true;
    if (!told) {
      told = true;
      onWaiting?.();
    }
    if (Date.now() + stepMs >= end) return false;
    await new Promise((resolve) => setTimeout(resolve, stepMs));
  }
}
