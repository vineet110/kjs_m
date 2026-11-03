// Small shared state for the staff portal, in this browser tab only.

// ----- The remembered account -----
// Admin and employee pages each have their own frame (PortalShell), so moving between them starts a new
// frame: with the account remembered, the page shows at once and the account is re-checked in the background.
// Filled and read only in the browser (the server never fills it, so it can't leak between visitors).
// Forgotten on log out, on "not logged in" (401), on a full reload, and whenever the login page opens or
// someone logs in: so a new person on the same tab never sees the previous person's name (PR #17 review).
let known: { id: number; name: string; email: string; role: 'admin' | 'employee'; permissions: string[] } | null = null;
// Goes up on every forget. A "who am I" answer may only be remembered if nothing was forgotten since it
// was asked: a slow answer that arrives after a log out can't bring the old account back (PR #17 review).
let epoch = 0;

export const rememberedAccount = () => known;
/** Call before asking "who am I"; pass the result to rememberAccount() with the answer. */
export const accountEpoch = () => epoch;
export function rememberAccount(me: NonNullable<typeof known>, askedAt: number) {
  if (askedAt === epoch) known = me;
}
export function forgetAccount() {
  known = null;
  epoch++;
}

// ----- "Something was approved" -----
// The sidebar's Approvals badge listens for this, so its count drops right after an approve / reject on
// the same page (not only after moving to another page; PR #17 review).
const APPROVALS_CHANGED = 'kjs:approvals-changed';

export function approvalsChanged() {
  window.dispatchEvent(new Event(APPROVALS_CHANGED));
}

/** Calls `fn` on every approvalsChanged(); returns the function that stops listening. */
export function onApprovalsChanged(fn: () => void) {
  window.addEventListener(APPROVALS_CHANGED, fn);
  return () => window.removeEventListener(APPROVALS_CHANGED, fn);
}
