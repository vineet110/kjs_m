# Learning log

2 or 3 lines a day, in your own words. Newest at the top.

Tag who wrote it: (V) Vineet, (T) teammate.

A word you don't know? Look it up in `../kb.md` (Ctrl + F).



---------------------------------------------------------------------------------------------------

## 9 Nov 2026 (frontend safety, board check, e2e tests: PRs #41, #46, #49, Nishita)

1. (T) A time-out on a save doesn't mean "not saved": the server may finish anyway. Say "may have been saved,
   check first", or people click again and save twice.

2. (T) A failing test is not a bug until you read why. Most of today's failures were tests out of date with the
   screens, or a deliberate change (a switched-off feature now says 404).

3. (T) Before running tests, check where they write: our `.env` sent test uploads to the real R2 bucket.

4. (T) Stopping a background shell may leave its server running. Check the port, or the next run tests old code.



---------------------------------------------------------------------------------------------------

## 9 Nov 2026 (go-live safety, PRs #42–#45, Vineet)

1. (V) A review finding is not automatically a fix: check each one against the code. 6 of 10 were real.

2. (V) CI runs the whole test suite on every PR. Locally, run only the tests of what you touched.

3. (V) Docker compose: `environment:` beats `env_file:`. One line blanks a secret for one service.

4. (V) Git Bash on Windows: native tools can't open `/tmp/...` paths. Let the shell open files with `<` and `>`.

5. (V) Scripts that patch files: use raw strings. `"\r"` and `"\1"` silently became control characters.



---------------------------------------------------------------------------------------------------

## 6–9 Nov 2026 (R2 pictures, order boards PRs #32, #35–#39, Vineet)

1. (V) Alembic picks `MIGRATION_DATABASE_URL` before `DATABASE_URL`. Setting only one sent my "local" check to
   Neon. Always set both, and run `alembic current` first to see where you are.

2. (V) A key pressed inside a frame (a PDF, a Word preview) never reaches the page. The browser's own full screen
   still closes on Esc.

3. (V) A CSV is just bytes: read it as UTF-8 text first, or ₹ and Hindi turn into junk.

4. (V) "Save the whole form" can undo someone else's newer save. Send back the version you started from.

5. (V) Reviewing each PR separately found different bugs than reviewing the whole stack at once.



---------------------------------------------------------------------------------------------------

## 7 Nov 2026 (lead management reviews, attendance, seed fix, PRs #33 and #34, Nishita)

1. (T) Tests that start the whole app can't find an import loop: by then everything is already loaded in a
   working order. Import each entry point alone in a fresh Python to catch it.

2. (T) A `datetime-local` box has no time zone. Say which zone you mean (`+05:30`), or the computer decides.

3. (T) "Same person" by phone OR email needs groups that join through a third lead. A single key per lead
   (phone, else email) splits people.

4. (T) Two PRs that add notes to the end of the same file always clash. Keep both blocks when merging.



---------------------------------------------------------------------------------------------------

## 3 Nov 2026 (admin redesign, PR #17, Nishita)

1. (T) A slow answer can arrive after the user has moved on (logged out, someone else logged in). Count the
   changes and keep only answers asked after the last one.

2. (T) When React moves an element, it can lose the pointer capture and the focus it had. Listen on the window
   during a drag, and give the focus back after the move.



---------------------------------------------------------------------------------------------------

## 2–3 Nov 2026 (UI steps 4 to 7, PR #16, Nishita)

1. (T) Show one label, keep the saved value. Renaming a saved value needs a migration and breaks old rows;
   renaming only the label is safe.

2. (T) A "save as it is" button that sends every field back can undo someone else's change. An edit should
   send only what changed, and the server should change only what it was sent.

3. (T) A picker that saves the same text as before needs no database change. Make data lists from a trusted
   library instead of typing them by hand, and read its output as UTF-8 (Windows guessed wrong: "TÃ¼rkiye").

4. (T) Python's `\d` also takes Arabic and full-width digits. Write `[0-9]` when you mean 0 to 9.



---------------------------------------------------------------------------------------------------

## 30 Oct – 3 Nov 2026 (CR1 restore fix, PR #13, Vineet)

1. (V) A check can pass without proving what you think. `pg_restore -l` passed backups cut in half, because
   it reads only the list at the start. Only reading the whole file caught them.

2. (V) In a pipe, the second program can't see that the first one failed. So we send it something that
   always errors, and the database cancels the whole transaction.

3. (V) Write the test first and watch it fail: that proves the bug is real. And a test proves only what it
   really tries: an easy fake crash missed the hard case (a crash inside a table's rows).

4. (V) Stopping a script doesn't stop what it started. When a script loses sight of a step, it must say
   "I don't know", not guess "nothing changed". Better still, ask the system that knows (the database).

5. (V) A warning alone is not enough after the data changed: every way out must say what changed and how
   to undo it. Pick file names yourself; don't read them back out of a message meant for people.

6. (V) AI reviews always find something new. Decide what blocks a merge with a fixed rule (real input, wrong
   result, realistic harm, a test can show it), and put the rest in the backlog.



---------------------------------------------------------------------------------------------------

## 2 Nov 2026 (PR #14 review, Nishita)

1. (T) Removing a block can remove spacing too: check the space between what is left, not just that it's gone.

2. (T) A test can't always break the code for real (the API down); break it on purpose instead (reverse the
   condition) and see the test fail. Then put the code back.

3. (T) Read the list to test from the page itself (the footer links), not a copy in the test that can drift.


## 31 Oct 2026 (home removals, Nishita)

1. (T) `innerText` skips parts hidden at this screen width; `textContent` reads them too. A "removed" check must
   use `textContent`, or it passes just because the window is small.

2. (T) A test that fails on leftovers from the last run is not a code bug: start from a fresh test database.


## 31 Oct 2026 (sliding sidebar, Nishita)

1. (T) Animate `transform` (slide), not width or padding: the browser moves it cheaply, no page re-layout.

2. (T) A hidden menu must also be unreachable: `inert` stops Tab and screen readers from finding it.

3. (T) An overlay on a phone must lock the page behind it and give focus back to the button when it closes.


## 31 Oct 2026 (PR #12 second review, Nishita)

1. (T) Check a URL AFTER it is cleaned up, not before: "/..//evil.com" looks like our site, but becomes
   "//evil.com", which a browser opens as another website (open redirect).

2. (T) An answer we can't read is not "empty": for a success it is an error. `{}` passed off as data crashes
   later, far from the real cause.

3. (T) Node has a test runner built in (`node --test`): unit tests without adding a package.

4. (T) A test can pass on my PC and fail in CI: different Node versions (24 here, 22 in CI). Node stops when
   nothing keeps it busy, and an AbortSignal.timeout timer doesn't; the time-out test now keeps Node running.



---------------------------------------------------------------------------------------------------

## 30 Oct 2026 (PR #12 review, Nishita)

1. (T) Every wait needs an end: a time limit for each request, and a way out on the error screen (Try again
   AND Log out). A screen with only "Try again" can still be a dead end.

2. (T) A time limit can lie: a slow sign-up may still succeed. Only put a limit where "try again" is harmless
   (logging in again is fine; creating an account twice is not).

3. (T) Put the test in the repo, not only on my PC, so others can run it and see it fail on the old code.



---------------------------------------------------------------------------------------------------

## 30 Oct 2026 (login spinner, Nishita)

1. (T) To keep a "loading" state on while the page changes, don't skip the reset and hope the page goes
   away: React's useTransition says when the page change is really done, in every case.

2. (T) A loading screen needs an end: if the request fails (not "logged out"), show an error and "Try again",
   or the visitor watches a spinner forever.

3. (T) Prove a test can fail: run it on the old code first (git stash), then on the new code.



---------------------------------------------------------------------------------------------------

## 30 Oct 2026 (PR #9 fifth review, Nishita)

1. (T) Fixing a rare case can create a common one: keeping "unknown" products (for two tabs on different
   site versions) also kept products taken off the site, which happens far more often. Ask how often each
   case really happens.

2. (T) A test is only worth something if it can fail: run it against a deliberately broken version of the
   code and see it catch the bug. Random inputs find cases you didn't think of, but check they really
   reach the hard case (here: lists over the limit).

3. (T) An effect runs after the page draws: read the LATEST saved data there, not the value from when the
   page drew.



---------------------------------------------------------------------------------------------------

## 29 Oct 2026 (whole-repo code review)

1. (V) `a | b` in a shell only reports whether `b` worked. Our restore piped `pg_restore` into `psql`: a bad
   backup file could empty the database and the script would still say "done". Check inputs before deleting anything.

2. (V) "200 OK" doesn't always mean the page works. With `loading.tsx`, Next.js sends 200 before the page has
   finished, so a health check must call something that really fails when things are broken.

3. (V) Limits "per IP" are tricky: an office shares one IP (blocks our own staff), while one IPv6 home has
   billions of addresses (a bot walks around the limit). Count IPv6 by /64 block, count only failed logins.

4. (V) A fix nobody has run is a guess. Three review rounds kept finding bugs in code snippets written in a
   document, while the problem descriptions held up. So: a failing test first, and no code snippets in docs.



---------------------------------------------------------------------------------------------------

## 29 Oct 2026 (PR #9 fourth review, Nishita)

1. (T) An IntersectionObserver sees an element's MOVED box (with its transform). An entrance that slides
   a card can slide it out of view, which hides it, which brings it back… A loop. Leave a margin bigger
   than the slide.

2. (T) One observer, one exact question is clearer and cheaper than one observer with many thresholds and
   extra checks.

3. (T) A limit needs a rule for what goes when it is hit. "Keep the newest" is simple and predictable,
   even if, in a rare case, an older product goes.



---------------------------------------------------------------------------------------------------

## 29 Oct 2026 (PR #9 third review, Nishita)

1. (T) A cache needs to know when it may be stale. If only listeners clear it, it goes stale while nobody
   listens (e.g. on another page). Drop it when the last listener leaves.

2. (T) Decide things at the moment they happen, not ahead of time: a card picks its entrance direction as
   it comes in, so nothing that happened while it was off screen can make it wrong.

3. (T) A form should work on the data as it was when it opened (a snapshot), or a change elsewhere can alter
   what is sent behind the user's back.

4. (T) A test that fakes a browser event must fake it the way the browser really sends it (the storage event
   carries the new value). A fake missing a field tested the wrong case.



---------------------------------------------------------------------------------------------------

## 29 Oct 2026 (PR #9 review, Nishita)

1. (T) A test that passes can still be wrong: one check passed because its click never happened, another
   only because of the very bug a review found. Make tests prove their setup (did the click land?).

2. (T) Data shared between tabs: only change what you are about (add or remove one item) in the latest saved
   copy, never save your whole old copy back; it may miss what another tab added.

3. (T) "Storage blocked" and "storage full" are different: a full store can still be read. Fall back to memory
   for what failed only, not for everything.



---------------------------------------------------------------------------------------------------

## 29 Oct 2026 (recommendations, Nishita)

1. (T) Pull first, then push. We fetched Vineet's work and merged it into our branch before fixing and testing,
   so everything was tested on the code that will really be pushed.

2. (T) "Personal" features can stay private: the recommendations use only what is stored in the visitor's own
   browser. Nothing about them is sent to our server.

3. (T) Two reviews can pull in opposite directions ("no flash" vs "server-render the content"). Look for the
   fix that satisfies both: server-render a real default, swap in personal picks quietly.

4. (T) A feature that hides content must have a way back to visible in every case: scroll, jumps, tab switches,
   and printing.



---------------------------------------------------------------------------------------------------

## 28 Oct 2026 (database move)

1. (V) A Neon project's region is fixed when it is created. "Changing region" means a new project, then
   migrations + seed (or copying the data), then new URLs in `.env`. Each folder has its own `.env`: v1 and v2
   both had to be changed.

2. (V) Moving the database close to us cut one trip from about 560 ms to about 80 ms. But one request can make
   several trips (check the connection, begin, run, end), so even a one-query page still waits about 0.5 s.

3. (V) A re-review looks at the latest commit, not the old one. Submit it as a new review (Request changes or
   Approve), so the PR's status matches the code that is there now.

4. (V) `git pull` refused because a generated file (`next-env.d.ts`) had changed locally. Generated files can
   be thrown away (`git restore`); the tool makes them again.



---------------------------------------------------------------------------------------------------

## 28 Oct 2026 (third review)

1. (T) Run every test suite the project has, not only the ones you know: the end-to-end browser test still
   looked for the old home page text, and nothing else would have caught it.

2. (T) A fallback that can never run is a bug in disguise: the backend always sends a default text, so the
   new wording written in the frontend never showed. Change the text where it really comes from.

3. (T) Check a "duplicate" against the source before deleting it: Pacho Fret 663 and 664 are both cocoa,
   but in two different packs. The fix was a clearer label, not a deletion.



---------------------------------------------------------------------------------------------------

## 28 Oct 2026 (second review)

1. (T) A reviewer's suggested fix is a suggestion: check it against the source. Next's <Link> always calls
   preventDefault(), so "only start the bar if the click wasn't cancelled" would never start it.

2. (T) Test like a user, not like a script: move the mouse slowly across gaps, use only the keyboard, turn
   optional parts on (the offers ticker), and try a phone-sized screen. Each of these found a bug.

3. (T) Keep a PR small. Every new feature added to an open PR gave the reviewer new code to find bugs in.

4. (T) Content streamed by the server runs no JavaScript until the page is ready. To react to a loading
   screen on a fresh load, use CSS (`body:has(...)`), not a React effect.



---------------------------------------------------------------------------------------------------

## 28 Oct 2026 (review fixes)

1. (T) A CSS transform changes what "fixed" means for everything inside it: a full-screen popup inside a
   transformed box only fills that box. Centre without transforms, or draw popups into <body> (a portal).

2. (T) Data saved in the browser can go stale: a product can be hidden or deleted later. When loading saved
   data, keep only what still exists.

3. (T) Every limit must count everything that goes into it: 20 products fit in 4000 characters, but the
   buyer's own note did not, so the whole lead could be refused.

4. (T) Test with a throwaway database when a test writes data (here: sending an enquiry), never the shared one.

5. (T) A loading.tsx makes the page stream: headers (and the 200 status) go out before the page decides it is
   "not found". So a missing product answered 200, not 404. Keep loading.tsx away from pages that call notFound().

6. (T) An animation that hides content must always have a way back to visible: content that moves into view
   without a scroll (a tab switch) or that you jump past must still appear. Test with fast jumps, not slow scrolls.

7. (T) Testing your own work only finds what you thought of. The independent review found 10 issues my tests missed.



---------------------------------------------------------------------------------------------------

## 27 Oct 2026 (catalogue and new home page)

1. (T) The database stores only the path of an image, never the image itself. The file goes to a folder
   (`storage/` on our PC, Cloudflare R2 in production). Databases are slow and costly for big files.

2. (T) The frontend has no `requirements.txt`: JavaScript projects list their packages in `package.json`
   (and exact versions in `package-lock.json`). `npm ci` is the frontend's `pip install -r requirements.txt`.

3. (T) Two people working in parallel: keep your change in NEW files when you can. The catalogue seed is its own
   file (`seed_catalogue.py`), so it didn't clash with Vineet's backend work. The docs did clash: we both
   added A67, so mine became A73. Pull often, before writing new numbers.

4. (T) "500 error" on the home page with `ECONNREFUSED 127.0.0.1:8000` means the backend is not running.
   Start the backend first, then the frontend.

5. (T) "An Application Control policy has blocked this file" = Windows Smart App Control. Docker runs the
   backend in Linux, where Windows can't block it.



---------------------------------------------------------------------------------------------------

## 27 Oct 2026 (production-readiness review)

1. (V) Tests check what the code does on a good day; production is the bad days. The worst findings were
   "what if": the mail server is down, a deploy changes container addresses, someone types a config typo.

2. (V) A background job that dies must be noticed. Our health check said "OK" while emails and SLA alerts
   could have stopped forever. Now the jobs loop leaves a heartbeat and `/api/health/ready` checks it.

3. (V) An empty field means "no change", not "erase". Approving "I forgot to punch in" wiped the real
   check-out because the request had no check-out.

4. (V) A failing test is not always a bug in the app. The e2e "auto-assign" failure was the background job
   doing its work one second before the test. Read the log before "fixing" anything.

5. (V) Security limits can be turned against the owner: a lock per email let a stranger lock the admin out.
   Lock the attacker (email + network), not the victim.



---------------------------------------------------------------------------------------------------

## 26 Oct 2026 (speed and Smart App Control)

1. (V) Measure before you fix. "Koko is slow, is it the free tier?" The numbers said: each database query takes
   about 560 ms because Neon is in the USA. Distance, not the price plan, was the main cost.

2. (V) A page that runs 5 queries one after another pays the network delay 5 times. Keep the database close to
   the app (same server in production, Docker on this PC for development).

3. (V) Turning a security feature off is a trade-off, not a free fix. Write down why, and what still protects you.

4. (V) Big upgrades go on their own branch. Next 14 → 16 was done on `next16`; if anything broke, delete the
   branch and `kjs_v` / `main` are untouched. Merge only after every check passes.

5. (V) Check every package before a major upgrade: does it support the new version (peer dependencies)?
   One unused package (`lucide-react`) would have blocked React 19. Unused packages are pure risk.

6. (V) Read the upgrade guide's "breaking changes" and search the code for each one (`params`, `cookies()`,
   `middleware`). Counting the affected files turned a "2 days" guess into a half-day job.



---------------------------------------------------------------------------------------------------

## 25 Oct 2026 (senior review)

1. (V) Every check must happen BEFORE the expensive or risky step. The login lock only counted wrong
   passwords, so after 10 wrong guesses the right one still worked: an attacker just waits for the one "200".
   Check "is this email locked?" first, then the password.

2. (V) A permission is not a role. Giving someone `staff.approve` quietly made them an admin, because
   "approve" could also re-permission any account, including their own. Ask for every power: "can they use it
   on themselves, or on someone above them?"

3. (V) Links are code. `<a href="javascript:...">` runs JavaScript as our site when clicked. Any link that
   comes from data (even from staff) must be checked: only `/our-page` or `https://`.

4. (V) "Read, change, write back" breaks when two people click at the same moment. `SELECT ... FOR UPDATE`
   locks the row until the change is saved, so the second click waits and then sees the new state.

5. (V) Least privilege: the app's database user may read and write rows, nothing more. If the app is ever
   tricked into running bad SQL, it can't drop tables, edit the audit log, or run server commands.

6. (V) A small file can be huge inside: an .xlsx is a zip, and 60 KB can unpack to gigabytes. Check the
   unpacked size before opening it.

7. (V) An independent reviewer finds what the author can't see. All four reviews found real problems in
   code that already had 125 passing tests: tests only check what you thought of.



---------------------------------------------------------------------------------------------------

## 25 Oct 2026 (production setup)

1. (V) Test the production setup like production. Running the whole stack locally found 4 things that reading
   the files never would: the old nginx config cut `/api` off every address (every API call would be 404),
   `docker compose run` has no `--no-build` flag, Next.js and nginx both sent `Cache-Control`, and production
   logs were in the "pretty" format instead of JSON.

2. (V) A backup is only proven by a restore. The drill was: back up → delete the leads and a file on purpose →
   restore → count again. Same numbers before and after = the backup works.

3. (V) Fail loudly at start-up. If production starts with a default secret or a localhost address, it is
   better that it refuses to start (and says why) than runs with a hidden security hole.

4. (V) Never run containers as root, and open no ports to the internet. Cloudflare Tunnel connects out from
   the server, so there is nothing to attack from outside.

5. (V) Windows Smart App Control can suddenly block programs it doesn't trust, like the small `python.exe`
   inside `.venv`. The error says "Application Control policy". The base Python still works.

6. (V) Git Bash rewrites paths like `/srv/files` into `C:/Program Files/Git/srv/files` before passing them to
   Docker. `MSYS_NO_PATHCONV=1` turns that off. On a Linux server it never happens.



---------------------------------------------------------------------------------------------------

## 24 Oct 2026 (morning: commit, push, docs clean-up)

1. (V) Check before you commit. Before pushing 154 changed files we searched the staged changes for secrets
   (API keys, passwords) and for files that must never be committed (`.env`, storage folders, `.next`).

2. (V) A doc nobody can read is a doc nobody uses. Long tables are hard to read in a plain editor;
   numbered lists with blank lines are easier. One glossary (`kb.md`) beats many small learning files.

3. (V) Starter repos bring packages you don't use. `package.json` still lists 9 packages no code imports.
   Unused packages slow installs and add security risk; remove them (after asking).



---------------------------------------------------------------------------------------------------

## 24 Oct 2026 (night: all of Phase 1 + end-to-end testing)

1. (V) Test the real thing, not only unit tests. 121 unit tests passed, yet the end-to-end run on real servers
   found 2 serious bugs. Unit tests check pieces; e2e checks the pieces together (proxy, cookies, cache,
   database restarts).

2. (V) Behind a proxy, the "client IP" is the proxy. Next.js forwards every browser call, so the API saw
   127.0.0.1 for everyone: one visitor's 5 enquiries would block the whole website. Read the real IP from
   `X-Forwarded-For` / `CF-Connecting-IP`, but only when the request comes from our own proxy
   (otherwise anyone can fake it).

3. (V) Speed tricks can break correctness. Turning off `pool_pre_ping` saved 0.5 s per call, but after the
   database dropped connections (Neon sleeps after 5 minutes) the next request failed. Fix slowness at the
   cause (database far away), not by skipping safety checks.

4. (V) Python's `round()` is banker's rounding: `round(2.5) == 2`. For business numbers people expect 3;
   use `int(x + 0.5)` for positive numbers.

5. (V) Next.js caches `fetch` by address + headers. Adding a unique header (a request ID) to every server
   fetch would silently turn the cache off.

6. (V) Two test runs on one test database wipe each other's data. Run the suite once at a time.

7. (V) Settings you can change without a deploy: secrets in `.env`, tunable numbers in `config/*.ini`
   (re-read every few seconds), and the code reads them at the moment of use (`cfg().sla.respond_minutes`),
   never copied into a constant at start-up.

8. (V) Store keys, not files, in the database. Files go to storage (disk now, Cloudflare R2 later);
   the database keeps the key, name, size and owner.



---------------------------------------------------------------------------------------------------

## 23 Oct 2026 (session 3b)

1. (V) Prompt order matters. Koko kept promising "50,000 sticks/month is fine". Moving the rules after the long
   facts block, plus one good and one bad example, fixed it. Always test the AI with tricky questions.

2. (V) Check the server really restarted. A stale API process kept serving old code, and the tests looked wrong
   for the wrong reason. If nothing changes after an edit, check which process is on the port.

3. (V) Catch-all routes need checks. `[locale]` accepted anything, so `/robots.txt` showed the home page.
   Unknown values must give 404.



---------------------------------------------------------------------------------------------------

## 23 Oct 2026 (session 3: first code)

1. (V) Proxy instead of CORS. The browser talks only to Next.js; Next.js forwards `/api/*` to FastAPI.
   The login cookie stays on one site, so much less CORS and cookie setup.

2. (V) httpOnly cookie + random token in the database. JavaScript can't read the cookie (XSS can't steal it);
   we store only a hash of the token, so a database leak can't log anyone in. Logout = delete the row.

3. (V) CSRF header trick. Every POST / PATCH must carry `x-requested-with`. Another website can't add custom
   headers to requests to us, so it can't fake actions with your cookie.

4. (V) Audit trigger. A Postgres trigger raises an error on UPDATE / DELETE of `audit_log`, so even buggy code
   can't rewrite history.

5. (V) Pooled vs direct database address (Neon). The pooler shares connections between clients, so asyncpg's
   prepared-statement cache must be off; migrations use the direct address.

6. (V) Honeypot. A hidden form field. People leave it empty, bots fill it, so we silently drop those.



---------------------------------------------------------------------------------------------------

## 23 Oct 2026 (session 2)

1. (V) Docker on Windows runs inside WSL 2 (a small Linux inside Windows). "WSL not installed" just meant that
   part was still installing.

2. (V) `make` turns long commands into short ones (`make up`). Handy, not required.

3. (V) Design for change. Put things that may change (AI provider, file storage, database host) behind one module
   and one setting, so switching later is a setting change, not a rewrite.

4. (V) Permissions vs roles. Code checks a permission ("can approve leave"); a role is just a default bundle of
   permissions. Giving one employee an extra permission then needs no code change.



---------------------------------------------------------------------------------------------------

## 23 Oct 2026

1. (V) Before coding, read every document and list where they disagree. Newer documents usually win, but
   someone has to decide and write it down (`backlog.md` decisions).

2. (V) A plan with dates must be re-planned the moment reality differs. Saying "we're 1 week behind" early is
   professional, not a failure.

3. (V) Our stack in one line: Next.js shows the pages, FastAPI owns the data and rules, Postgres stores
   everything, an AI model powers Koko.
