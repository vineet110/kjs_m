@AGENTS.md

# Frontend (Next.js)

Project rules: `docs/prompt.md` section 3. This file: how to run and check.

1. Typecheck: `npx next typegen` once (route types are generated, not in git), then `npx tsc --noEmit`.

2. Tests: `npm test` (Node's built-in runner, `tests/lib.test.mjs`, covers `src/lib`).

3. Build: `npm run build`. Dev server: `npm run dev`.

4. Don't commit a changed `package-lock.json` unless a dependency change was agreed.

5. Limits the server also checks (message length, word minimums) come from `me.limits` (`/auth/me`, from
   `config/*.ini`). Keep only a fallback number in the frontend, never a second source of truth.
