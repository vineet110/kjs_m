# WhatsApp demo video: summary (I8)

> Source: `WhatsApp Video 2026-10-23 at 13.14.24.mp4` (3 min 11 s, no login, "DEMO · SAMPLE DATA").
> Read from screenshots taken every 4 seconds on 23 Oct 2026. Audio was not checked.
> Title in the video: **"KJS Buyer Intelligence": Website · AI assistant · Partners · Employee portal · Admin panel**

## The story, in order
| # | Who | Screen (URL) | What happens |
|---|---|---|---|
| 1 | Employee | `/employee` | Priya signs up (name, work email, department, password) → **email verified** → "waiting for admin approval" |
| 2 | Admin | `/admin/overview` | Separate admin login. Cards: new chatbot leads, waiting for approval, new partner applications, tasks past SLA. Nightly scheduler pipeline (Fetch → Extract → Clean → Validate → Duplicate check → Save) + off-site backup status |
| 3 | Admin | `/admin/employees` | Approves Priya and **ticks her permissions**: receive chatbot leads, search buyer DB, upload files, export to Excel |
| 4 | Customer | `/` | Public home, no login. Hero "Trusted Co-Manufacturing Partner", 4 categories (coffee, tea, health drinks, confectionery), featured products |
| 5 | Customer | `/products`, `/products/c3in1` | Whole site switches to Spanish (8 languages in the menu). Product page shows **price in USD per 1,000 units** + currency converter (EUR, GBP, INR, AED…), format, size, MOQ, shelf life, "available as private label" |
| 6 | Customer | Koko chat | Asks in Spanish → Koko answers in Spanish from the catalogue → buyer says "20,000 sachets/month" → Koko collects **name, phone, email** → hands over to **WhatsApp** with a pre-filled message to KJS Sales |
| 7 | Customer | `/products/...` | "Connect with Sales" button also opens WhatsApp: no lead is missed |
| 8 | Partner | `/partners` | "Sell with us, earn commission": brokers, retailers, B2B, freelancers, affiliates apply (email verification) |
| 9 | Admin | `/admin/leads` | Lead card: contact, product, quantity, **AI chat summary**, chat language, sent to admin + permitted employees, "moved to WhatsApp" |
| 10 | Admin | `/admin/buyers` | Buyer database split by product type, **export to Excel, share with an employee**, each record shows its **source** (ITC Trade Map, company website, trade-fair PDF, UN Comtrade) |
| 11 | Admin | `/admin/data` | Sources & nightly scheduler (02:00): ITC Trade Map file inbox, UN Comtrade API, company websites, team uploads, Volza (paid). "Run scheduler now" |
| 12 | Admin | `/admin/tasks` | Assign task with SLA (respond 20 min, resolve 1 h default) → live countdown |
| 13 | Admin | `/admin/work` | Daily work: what each person did and how long it took |
| 14 | Admin | `/admin/backups` | Nightly encrypted off-site backup, kept 30 days, restore tested weekly |
| 15 | Admin | `/admin/audit` | Audit log with filters (approvals, DB changes, exports & sharing, settings, system). Cannot be edited |
| 16 | Employee | `/employee/home` | "My day": my tasks with SLA timers, new lead for me, shared with me, buyer DB, upload files, **today's work log** (task + time taken) |

## Where the video differs from our Stage 1 plan
| Video shows | Our plan | Action |
|---|---|---|
| Buyer database, data sources, nightly scraping scheduler | **Stage 2** (2027) | ⚠️ Make sure the company knows this is not in the 11 Dec launch (D18) |
| Partner programme + commissions | Stage 2 | Same as above |
| 8 languages | English at launch (D2) | Fine, next-intl keeps the door open |
| Public USD prices + currency converter | Price sheet via a form (I3) | Decide (D19) |
| Koko → WhatsApp hand-off (wa.me link) | Koko → enquiry form → lead | Easy add: a `wa.me` link needs no Meta approval |
| Per-employee permission ticks at approval | D5 permissions | ✅ Matches |
| Email verification on employee sign-up | Admin approval only | Add (small) |
| Daily work log (task + time) | Tasks + notes | Add to Phase 3 |
| **Not in the video:** attendance, order boards, auto-assign, deadline alerts | Stage 1 | They're still in our plan; the video just doesn't show them |
