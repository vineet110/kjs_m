# Frontend test cases: live site

- **Site:** https://kjs-m.vercel.app (frontend on Vercel, backend on Render)
- **Date:** 12 Nov 2026 · **Tester:** Nishita (S) · **Code:** `main` at `4880aa5` (PR #68)
- **Method:** HTTP requests (`curl`), read-only. Nothing was submitted, created or changed on the site.
- **Not run yet:** tests that need a logged-in browser (section 4). The Chrome extension wasn't connected.

Result key: **Pass** · **Fail** · **Not run**

## 1. Summary

| Area | Cases | Pass | Fail | Not run |
|---|---|---|---|---|
| Backend health | 2 | 2 | 0 | 0 |
| Public pages | 7 | 7 | 0 | 0 |
| Sitemap pages (categories + products) | 86 | 86 | 0 | 0 |
| Wrong addresses (404) | 4 | 4 | 0 | 0 |
| Logged-out access to the portal | 2 | 2 | 0 | 0 |
| API without login | 2 | 2 | 0 | 0 |
| Site setup (sitemap, robots, headers) | 3 | 0 | 3 | 0 |
| Logged-in portal (browser) | 12 | 0 | 0 | 12 |

## 2. Test cases run

| ID | Test | Steps | Expected | Actual | Result |
|---|---|---|---|---|---|
| T1 | Backend is up | GET `/api/health` | 200, `status: ok` | 200 in 0.4 s, `{"status":"ok","service":"kjs-api"}` | Pass |
| T2 | Frontend health | GET `/healthz` | 200 | 200 in 2.5 s | Pass |
| T3 | Home page | GET `/` | 200 | 200 | Pass |
| T4 | Products page | GET `/products` | 200 | 200 | Pass |
| T5 | Contact page | GET `/contact` | 200 | 200 | Pass |
| T6 | Partners page | GET `/partners` | 200 | 200 | Pass |
| T7 | Private label page | GET `/private-label` | 200 | 200 | Pass |
| T8 | Login page | GET `/employee/login` | 200 | 200 | Pass |
| T9 | English locale | GET `/en` | Goes to `/` | 307 → `/` | Pass |
| T10 | Every sitemap page opens | Read `/sitemap.xml`, open each path on the live site | 86 × 200 | 86 of 86 returned 200 (9 categories, 77 products, home + 5 pages) | Pass |
| T11 | Unknown page | GET `/this-page-does-not-exist` | 404 page | 404 | Pass |
| T12 | Unknown product | GET `/products/no-such-product` | 404 | 404 | Pass |
| T13 | Unknown category | GET `/categories/no-such-cat` | 404 | 404 | Pass |
| T14 | Unknown locale | GET `/hi` | 404 | 404 | Pass |
| T15 | Admin page when logged out | GET `/admin/dashboard` | Sent to login | 307 → `/employee/login?next=/admin/dashboard` | Pass |
| T16 | Employee page when logged out | GET `/employee/dashboard` | Sent to login | 307 → `/employee/login?next=/employee/dashboard` | Pass |
| T17 | API: who am I, no login | GET `/api/v1/auth/me` | 401 | 401 | Pass |
| T18 | API: admin users, no login | GET `/api/v1/admin/users` | 401 | 401 | Pass |
| T19 | Sitemap uses the live address | Read `/sitemap.xml` | `https://kjs-m.vercel.app/...` | Every link is `http://localhost:3000/...` | **Fail** (B1) |
| T20 | robots.txt points to the live sitemap | Read `/robots.txt` | `Sitemap: https://kjs-m.vercel.app/sitemap.xml` | `Sitemap: http://localhost:3000/sitemap.xml` (the Disallow lines for /admin, /employee, /api are correct) | **Fail** (B1) |
| T21 | Security headers | Read the response headers of `/` | HSTS, CSP, X-Frame-Options, X-Content-Type-Options | Only HSTS | **Fail** (B2) |

## 3. Bugs found

### B1: Sitemap and robots.txt point to localhost

- **Seen in:** T19, T20.
- **Cause:** `frontend/src/app/sitemap.ts` and `robots.ts` use `process.env.SITE_URL || 'http://localhost:3000'`, and `SITE_URL` isn't set on Vercel.
- **Effect:** Google gets 86 links it can't open, so the site's pages aren't indexed properly.
- **Fix (no code change):** in Vercel → Settings → Environment Variables, set `SITE_URL=https://kjs-m.vercel.app` and redeploy. Change it again once the real domain is picked (backlog D7).

### B2: Security headers missing on Vercel

- **Seen in:** T21.
- **Cause:** CSP, X-Frame-Options and X-Content-Type-Options are set in `deploy/nginx/security-headers.conf`. Vercel doesn't use our nginx, so they're never sent. This is the same reason `config/*.ini` isn't used on Render.
- **Effect:** the live site has no protection against being framed (clickjacking) and no CSP.
- **Fix (needs a decision):** add the same headers with `headers()` in `frontend/next.config.mjs`, or in a `vercel.json`. The CSP image list has to match where pictures load from (R2).

## 4. Not run yet: needs a logged-in browser

To run once the Claude Chrome extension is connected, with each test account (V, S, K). All of them are read-only.

| ID | Test | Expected |
|---|---|---|
| L1 | Log in with the test account | Dashboard opens |
| L2 | Wrong password | Error message; no login |
| L3 | Sidebar areas match the role | Only the allowed areas are shown |
| L4 | Only one sidebar group open at a time | Opening one group closes the other (PR #68) |
| L5 | Every sidebar page opens | No error screen |
| L6 | No console errors on any page | Console is clean |
| L7 | Bell clears when clicked | Count goes to 0 (PR #68) |
| L8 | Partners tab shows a count | Count is shown (PR #68) |
| L9 | "Tasks & Track" name in the sidebar | New name is shown (PR #67) |
| L10 | Employee opens an `/admin/...` page | Refused or sent away |
| L11 | Admin opens `/admin/...` pages | Pages open |
| L12 | Log out | Back to login; `/employee/dashboard` sends you to login again |

## 5. How to repeat the HTTP checks

```bash
B=https://kjs-m.vercel.app
for p in /api/health /healthz / /products /contact /partners /private-label /employee/login /admin/dashboard /this-page-does-not-exist; do
  echo "$p -> $(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' $B$p)"
done
curl -s $B/robots.txt
curl -sI $B/ | grep -iE "strict-transport|x-frame|content-security|x-content-type"
```
