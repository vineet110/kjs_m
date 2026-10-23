# Backlog: blockers, decisions, inputs, later

> Anything stopping us, any open decision, anything we've postponed.
> When something is solved, change its status to ✅ with the date. Don't delete it.

Status: 🔴 blocking now · 🟠 blocks a future phase · 🟢 not urgent · ✅ done

---

## 1. Blockers
| ID | Blocker | Blocks | Owner | Raised | Status |
|---|---|---|---|---|---|
| B1 | GitHub repo URL not shared. We need to clone it into `KJS_v1` (see note below) | Phase 1 | Vineet | 23 Oct | ✅ 23 Oct: github.com/vineet110/kjs_m checked out into `KJS_v1` (branch `main`). `docs/` + `CLAUDE.md` not committed yet |
| B2 | Dev tools. Present: Node 24, npm 11, uv 0.13, git 2.56, Python 3.11. ~~Missing: Docker Desktop, `gh` CLI~~ installed 23 Oct (Docker 29.8 + WSL 2, gh 2.103). `gh auth login` ✔ (vineet110), ffmpeg ✔. Still to do: `uv python install 3.12`. `make` optional | Phase 1 | Vineet | 23 Oct | 🟠 |
| B7 | Docker Desktop licence: free only for companies **under 250 employees AND under $10M revenue**. If KJS is bigger, it needs a paid seat, or we use a free alternative (Docker Engine inside WSL, Rancher Desktop, Podman) | Phase 1 | Manager | 23 Oct | ✅ 23 Oct: KJS fits the free tier |
| B9 | Secrets (Groq key, Neon password) were pasted in chat. Rotate both before go-live / before sharing the repo wider | Go-live | Vineet | 23 Oct | 🟢 |
| B10 | Neon project is in **us-east-2 (Ohio)**: slow from India. Fine for dev; production DB near India or on the company server | Staging | Vineet | 23 Oct | 🟢 |
| B11 | 23 Oct work is **not committed**. Review, then commit on branch `feat/p1-foundation` and open a PR | Phase 1 | Vineet | 23 Oct | 🟠 |
| B8 | Koko has no API key. We have Claude Max (a chat subscription; it can't power our website). Groq key available → use Groq for dev behind a provider switch (D4) | Phase 4 | Vineet | 23 Oct | 🟢 |
| B3 | Company server + IT contact + SSH access unknown | Staging (Phase 2) | Manager / IT | 23 Oct | 🟠 |
| B4 | Meta Business verification for WhatsApp: started? (can take 1–2 weeks) | WhatsApp alerts (Phase 6) | Manager | 23 Oct | 🟠 |
| B5 | Anthropic API key with a monthly spend limit | Koko (Phase 4) | Manager | 23 Oct | 🟠 |
| B6 | Domain / DNS access for kjsindia.com (Cloudflare, SPF/DKIM for email) | Staging, email | Manager / IT | 23 Oct | 🟠 |

> **Note on B1:** `docs/` already exists in `KJS_v1`, so `git clone <url> .` will fail. Use instead:
> `git init && git remote add origin <url> && git fetch && git checkout -b main --track origin/main` (rename the branch if it isn't `main`). Claude can do this once you share the URL.

## 2. Decisions needed from management
| ID | Question | Recommendation | Needed by | Status |
|---|---|---|---|---|
| D1 | Was the Next.js switch (plan v2) approved? | Yes, Next.js | 28 Oct | ✅ 23 Oct: Next.js (SEO) |
| D2 | Public languages at launch: EN only / EN+HI / EN+AR+ES+FR? | EN at launch, others as translation files after | 28 Oct | ✅ 23 Oct: English only at launch; next-intl stays so languages can be added later |
| D3 | Category gate: form before categories (v1) or only on actions (v2)? | Actions only (v2), better for SEO | 28 Oct | ✅ 23 Oct: **actions only (v2)**. Browsing is free; the form appears on price sheet / sample / enquiry. General rule: anything that blocks us moves to a later release |
| D4a | Koko early test (23 Oct, 1 tricky question × 3 Groq models): gpt-oss-120b, gpt-oss-20b, qwen3.8-27b all followed the rules once the rules were placed *after* the facts. Keep gpt-oss-120b; run the full 30-question test in Phase 4 | | 13 Nov | 🟢 |
| D4 | Koko model + monthly budget | Dev: Groq behind an `LLM_PROVIDER` switch. Before go-live: test Groq vs Claude Haiku on 30 real questions, decide budget | 13 Nov | 🟢 Updated 23 Oct: no Anthropic API yet, use Groq for now |
| D5 | Roles at launch: what can a "manager" do? | admin, manager (read all, approve), employee | 28 Oct | ✅ 23 Oct: **admin + employee only**, no manager. Routes check *permissions*; role gives defaults; per-employee extra permissions if cheap (UI may slip to after go-live) |
| D6 | Superset at launch, or native charts first? | Native charts first; Superset after go-live | 28 Oct | ✅ 23 Oct: native charts first, **real DB data only, never fake numbers**; Superset after go-live |
| D7 | Domain: replace www.kjsindia.com, or use a subdomain? | Subdomain until the client decides | before go-live | 🟢 Postponed 23 Oct: decide at deployment time |
| D8 | Approve the re-baselined timeline in `track.md` (11 Dec target, 18 Dec latest) | Approve | 28 Oct | ✅ 23 Oct: approved. Company-facing copy: `trackEXP.md` |
| D15 | Hosting during development: Neon free Postgres now, move to the company server later? | Yes. Local dev uses Docker Postgres; Neon only for staging until the server is ready. Standard Postgres only, so the move is a `pg_dump` / `pg_restore` | Phase 2 | ✅ 23 Oct |
| D16 | Images / videos / files: where? | Never in the DB. One storage module (S3-compatible API); DB keeps only the file key | Phase 2 | ✅ 23 Oct: **Cloudflare R2** (S3-compatible, free tier, no download fees). Local dev: disk folder behind the same module |
| D18 | The demo video shows Stage 2 features (buyer database, data sources/scraper, partner programme, 8 languages). Does the company expect these on 11 Dec? | Tell them clearly: Stage 2 = 2027 (see `research/video-summary.md`) | 28 Oct | 🟠 |
| D19 | Video shows public USD prices + currency converter; plan says price sheet via form. Which one? | Show prices only where KJS gives them (I3); converter is cheap to add | 2 Nov | 🟠 |
| D17 | Repo folder names: existing repo uses `frontend/` + `backend/`, plan said `apps/web` + `services/api` | Keep `frontend/` + `backend/` (renaming gains nothing) | Phase 1 | 🟢 Proposed |
| D9 | Stage 1 auto-assign: what are the "records" in a batch? (leads? imported Excel lists?) | Leads + imported Excel lists | 13 Nov | 🟠 |
| D10 | Auto-assign: must the employee be checked in, or only Available? | Checked in **and** Available | 13 Nov | 🟢 |
| D11 | Late step: keep the final deadline (compress) or move it? | Admin chooses per board; default keep deadline | 20 Nov | 🟢 |
| D12 | Gate leads: OTP at launch? | No. Validation + rate limit + Turnstile | 2 Nov | 🟢 |
| D13 | WhatsApp to personal numbers (opt-in) or email only? | Email first, WhatsApp opt-in | 20 Nov | 🟢 |
| D14 | Payroll export format | Plain Excel unless they send a template | 6 Nov | 🟢 |

## 3. Inputs needed from KJS
| ID | Input | Needed by | Status |
|---|---|---|---|
| I1 | Logo, brand colours, photos (factory, products), first offers for the ticker | 2 Nov | 🟠 |
| I2 | Product list: category, pack formats, MOQ, certifications, best sellers, HS code | 2 Nov | 🟠 |
| I3 | Price bands for the configurator (per product × pack × qty, USD per 1,000) | 9 Nov (else hide configurator) | 🟢 |
| I4 | Employee list: name, email, phone, shift, categories; holiday list 2026–27 | 9 Nov | 🟠 |
| I5 | FAQs + policies for Koko | 13 Nov | 🟢 |
| I6 | Step task templates for order boards; who receives alerts | 20 Nov | 🟢 |
| I7 | 2–3 real requirement files (Excel/PDF/Word) | 20 Nov | 🟢 |
| I9 | Confirm stick-pack fill range: kjsindia.com says 0.9–3 g, but 3-in-1 coffee sticks are usually ~18 g (the demo video shows 18 g). Koko repeats the site text | 2 Nov | 🟠 |
| I8 | Summary of the WhatsApp demo video (Vineet) | 26 Oct | ✅ 23 Oct: `research/video-summary.md` |

## 4. Missing documents
| ID | Document | Matters for | Status |
|---|---|---|---|
| M1 | `research_01.pdf` (source feasibility, trials T1–T10) | Stage 2 | 🟢 |
| M2 | `research_01_implementation_plan.pdf` (Claude batch code samples) | Stage 2 | 🟢 |
| M3 | Client's original notes | Context | 🟢 |

## 5. Later (Release 2 / Stage 2)
| Item | Why later | Raised |
|---|---|---|
| Buyer Intelligence: sources, pipeline, review, scoring (A1–A4, E2) | Stage 2 plan, Jan–Apr 2027 | 15 Oct |
| Outreach: mailboxes, sequences, approvals (A5–A6) | Stage 2 | 15 Oct |
| P4 importer landing pages (programmatic SEO) | Needs Comtrade data + reviewed copy | 15 Oct |
| Samples, quotes (PDF), partner portal + commissions | Stage 2 | 15 Oct |
| Superset embedded analytics | Native charts first (D6) | 23 Oct |
| Additional public languages + Arabic RTL | D2 | 23 Oct |
| OTP for gate leads | D12 | 23 Oct |

## 6. Scope requests log
> Every new "can we also…" goes here with date and requester **before** anyone builds it.

| Date | Request | From | Decision |
|---|---|---|---|
| 23 Oct | Neon setup prompt: install Neon CLI, provision Neon Auth + object storage | Neon onboarding | Skipped: conflicts with plan (FastAPI auth, R2 files). Used the connection string only |
| 23 Oct | From the video: email verification on staff sign-up, daily work log (task + time), Koko → WhatsApp hand-off (`wa.me` link) | Demo video | Small; add to Phase 1 / 3 / 4 |
| | | | |
