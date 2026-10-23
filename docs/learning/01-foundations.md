# Foundations

## Git & GitHub (daily)
**Know:** clone, branch, add, commit, push, pull, PR, review, merge, rebase vs merge, resolving a conflict.
**Our flow:** `main` is always deployable → `feat/<phase>-<name>` branch → small commits → PR → review by the other person → CI green → squash merge.
**Good commit message:** `feat(attendance): auto-close open sessions at shift end`.
**Practice:** learngitbranching.js.org (first 2 levels) · git-scm.com/book (chapters 2–3).

## Terminal
**Know:** `cd`, `ls`, paths, environment variables, running scripts, reading an error from the bottom up.
On this Windows PC we have PowerShell and Git Bash. Docker and `make` commands are easier in Git Bash / WSL.

## HTTP & JSON (what every web dev must know cold)
- Request = method (GET/POST/PATCH/DELETE) + URL + headers + body. Response = status + headers + body.
- Status codes: 200 ok, 201 created, 400 bad input, 401 not logged in, 403 logged in but not allowed, 404, 409 conflict, 422 validation, 429 rate limited, 500 our bug.
- Cookies: `httpOnly` (JS can't read it), `Secure` (HTTPS only), `SameSite=Lax` (helps against CSRF).
- **Try:** open DevTools → Network on any site and read 5 requests.
- **Read:** developer.mozilla.org → "HTTP overview" and "HTTP cookies".

## Environment variables & secrets
Config that changes between machines (DB URL, API keys) lives in `.env`, never in code. `.env.example` lists every key with fake values. `.env` is in `.gitignore`.

## Docker (just enough)
- **Image** = a packaged app. **Container** = a running image. **Compose** = several containers defined in one YAML file (web, api, postgres…).
- Know: `docker compose up -d`, `logs -f api`, `exec api bash`, `down`, volumes (data that survives restarts).
- **Read:** docs.docker.com → "Get started" parts 1–3.

## CI (GitHub Actions)
On every push, GitHub runs lint + type checks + tests. Red CI means don't merge. It's a robot reviewer that never gets tired.
