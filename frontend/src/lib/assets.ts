// Site pictures and flags live in the Cloudflare R2 bucket `kjs-site-assets`, with the same paths as in
// frontend/public/ (images/..., flags/...). NEXT_PUBLIC_ASSET_BASE is the bucket's public address
// (r2.dev link for testing, later https://cdn.kjsindia.com). Empty = use our own public/ folder, as before.
// It is read when the frontend is built, so changing it needs a new build.
export const ASSET_BASE = (process.env.NEXT_PUBLIC_ASSET_BASE || '').replace(/\/+$/, '');

/** The address of a site picture or flag: on R2 when ASSET_BASE is set, otherwise unchanged.
 *  Only /images/ and /flags/ move: other paths (uploaded photos at /api/...) stay on our own site. */
export function asset(path: string, base: string = ASSET_BASE): string {
  return base && (path.startsWith('/images/') || path.startsWith('/flags/')) ? base + path : path;
}
