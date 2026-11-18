# Session notes (Vineet)

One subheading per task. Moved into the shared docs after the PR merges (see `docs/prompt.md` section 7).


## Next.js 16.4.3 -> 16.4.6 (18 Nov)

1. Fixes two moderate advisories (GHSA-mfr8-8qww-v76h, GHSA-vc7v-qv4w-wrv8: cache leaks across root params
   with `'use cache'` / `unstable_cache()`). We use neither, so we were not exposed. Patch release, no code
   change. Backlog R90 done.

2. `npm audit` still lists high alerts, for the backlog at the next fold:

   i.    Firebase 13 (via `@grpc/grpc-js` and firestore): npm's "fix" is a downgrade to Firebase 9 (wrong).
         Check whether a newer Firebase fixes it; we only use Firebase Auth in the browser.
   ii.   Tailwind 3's build tools (chokidar, micromatch, picomatch, fast-glob): build and dev only, not on
         the live site. Fix is Tailwind 4 (a major upgrade, own PR).
