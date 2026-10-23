# Learning log

> 2–3 lines per day, **in your own words**. Newest at the top. Tag who wrote it: (V) Vineet, (T) teammate.

## 23 Oct 2026 (session 3b)
- (V) **Prompt order matters:** Koko kept promising "50,000 sticks/month is fine". Moving the rules *after* the long facts block, plus one good/bad example, fixed it. Always test the AI with tricky questions.
- (V) **Check the server really restarted:** a stale API process kept serving old code, and the tests looked wrong for the wrong reason. If behaviour doesn't change after an edit, check which process is on the port.
- (V) **Catch-all routes need validation:** `[locale]` accepted anything, so `/robots.txt` rendered the home page. Unknown values must 404.

## 23 Oct 2026 (session 3: first code)
- (V) **Proxy instead of CORS:** the browser talks only to Next.js; Next.js forwards `/api/*` to FastAPI. The login cookie stays same-site, so far less CORS/cookie setup.
- (V) **httpOnly cookie + random token in DB:** JavaScript can't read the cookie (XSS can't steal it); we store only a hash of the token, so a DB leak can't log anyone in. Logout = delete the row.
- (V) **CSRF header trick:** every POST/PATCH must carry `x-requested-with`. Another website can't add custom headers to requests to us, so it can't fake actions with your cookie.
- (V) **Audit trigger:** a Postgres trigger raises an error on UPDATE/DELETE of `audit_log`, so even buggy code can't rewrite history.
- (V) **Pooled vs direct DB URL (Neon):** the pooler shares connections between clients, so asyncpg's prepared-statement cache must be off; migrations use the direct URL.
- (V) **Honeypot:** a hidden form field. Humans leave it empty, bots fill it, so we silently drop those.

## 23 Oct 2026 (session 2)
- (V) Docker on Windows runs inside **WSL 2** (a small Linux inside Windows). "WSL not installed" just means that part was still installing.
- (V) **make** is a free tool that turns long commands into short ones (`make up`). Handy, not required: the same commands can be typed directly.
- (V) Design for change: put things that may change (AI provider, file storage, database host) behind **one module + an env setting**, so switching later is a config change, not a rewrite.
- (V) **Permissions vs roles:** code checks a permission ("can approve leave"); a role is just a default bundle of permissions. Then giving one employee an extra permission needs no code change.

## 23 Oct 2026
- (V) Before coding, read every doc and list the conflicts between them. Newer docs supersede older ones, but someone has to *decide* and write it down (`backlog.md` decisions).
- (V) A plan with dates needs re-baselining the moment reality differs. Saying "we're 1 week behind" early is professional, not a failure.
- (V) Our stack in one line: Next.js renders pages, FastAPI owns the data and rules, Postgres stores everything (even the job queue), Claude powers Koko.
