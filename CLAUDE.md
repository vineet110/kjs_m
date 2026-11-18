# KJS India Platform

Read first: `docs/memory.md` (facts, rules, decisions), then `docs/prompt.md` (how to work with us), then the current phase in `docs/track.md`.

- Monorepo: `backend/` (FastAPI, SQLAlchemy, Alembic), `frontend/` (Next.js), `config/` (tunable `*.ini`, applied live), `deploy/` (VPS setup), `docs/`. Each of `backend/` and `frontend/` has its own `CLAUDE.md` with the commands.
- We are two freshers learning while building: plan first, explain the why, keep changes small, never add a dependency without asking.
- New feature: follow the checklist in `docs/prompt.md` section 3 (own `config/<feature>.ini`, no tunable numbers in code, module switch, permission, allowed + forbidden tests).
- End of every session: write notes only in your temp file (`docs/tempV.md` for Vineet, `docs/tempS.md` for Nishita). Don't edit `track.md`, `memory.md`, `backlog.md` or `learning/learning-log.md` on a task branch. Full rules: `docs/prompt.md` section 7.
