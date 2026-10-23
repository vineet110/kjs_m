# KJS India Platform: Plan & Progress

> A simple version of our project plan for the KJS team.
> The detailed technical version is `track.md`. Both are kept in sync.
> Last updated: **23 Oct 2026**

## What we are building
One website with three parts:
1. **Public website.** B2B buyers (retailers, distributors, importers, brands wanting private label) browse our products, ask for price sheets and samples, and chat with **Koko**, our AI assistant. Every enquiry is saved as a lead.
2. **Employee portal.** Staff mark attendance, see their tasks and leads, and work on order boards.
3. **Admin console.** Admin approves staff, assigns work, tracks orders and deadlines, and sees reports built from real data.

## Key dates
| | Date |
|---|---|
| Coding starts | Mon 26 Oct 2026 |
| Website scope frozen | Fri 6 Nov 2026 |
| **Go-live** | **Fri 11 Dec 2026** |
| Latest acceptable go-live | Fri 18 Dec 2026 |

## The plan, week by week
| # | Weeks | What gets done | You can see it when… | Status |
|---|---|---|---|---|
| 0 | 23–24 Oct | Read all documents, set up tools and repository | | ✅ Done |
| 1 | 26–31 Oct | Foundation: login, admin approval of new staff, admin / employee roles, activity history | Staff sign up, admin approves, they log in | 🟨 Started early, works on a laptop (23 Oct) |
| 2 | 2–7 Nov | Public website: home, categories, products, enquiry form, Google-friendly pages | A visitor asks for a price sheet and admin sees the lead | 🟨 First version works on a laptop; needs product list from KJS |
| 3 | 9–14 Nov | Employee portal: attendance, tasks, leads with response timers, team attendance report | Our team uses it for a full working day | ⬜ |
| 4 | 16–21 Nov | Automatic work assignment + Koko AI assistant | Work reaches the right employee; Koko creates an enquiry | ⬜ |
| 5 | 23–28 Nov | Order boards: 5 steps, members, files, deadlines | One order runs through all 5 steps | ⬜ |
| 6 | 30 Nov – 5 Dec | Approvals, deadline alerts by email, reports & charts, backups | Each alert arrives exactly once; backup restore works | ⬜ |
| 7 | 7–11 Dec | Testing with the KJS team, fixes, go-live | 🚀 Live | ⬜ |
| Buffer | 14–18 Dec | Spare week for anything that slipped + first-week support | | ⬜ |
| Stage 2 | 2027 | Buyer database and data sources (shown in the demo video), outreach emails, quotes, partner programme, more languages | | Later |

Status: ✅ done · 🟨 in progress · ⬜ not started · ⚠️ at risk

## Decisions made
| Topic | Decision |
|---|---|
| Website technology | Next.js (best for Google search ranking) |
| Languages | English at launch; other languages added later |
| User roles | Admin and Employee (no Manager role) |
| Reports | Built-in charts from real data at launch; advanced analytics tool later |
| Database & hosting | Free cloud database during development; moved to the KJS server before or after go-live |
| Images & videos | Cloudflare storage (R2) |
| Enquiry form | Visitors browse freely; the form appears only when they ask for a price sheet, sample or quote (better for Google) |
| AI assistant (Koko) | Free/low-cost AI provider during development; final choice tested before go-live |
| Domain (web address) | To be decided at deployment |

## What we need from KJS
| Item | Needed by |
|---|---|
| Logo, brand colours, factory and product photos, first offers | 2 Nov |
| Product list (categories, pack sizes, minimum order, certifications, best sellers) | 2 Nov |
| Employee list + holiday list 2026–27 | 9 Nov |
| Server access + IT contact | Before staging (early Nov) |
| WhatsApp Business verification started (for alerts) | ASAP, takes 1–2 weeks |
| FAQs and policies for Koko | 13 Nov |
| Order steps and who receives deadline alerts; 2–3 sample requirement files | 20 Nov |

## Updates from Vineet
> Add your changes here, newest at the bottom, in this format:
> `[update: <what it refers to>, <date>] <change>`

- [update: Roles, 23 Oct] Removed the Manager role. Admin and Employee only.

## Progress notes
- **23 Oct:** First working version on a laptop. The public website uses the real KJS logo, photos, videos and text from kjsindia.com. Visitors can send enquiries or chat with the AI assistant (it answers in their language and never quotes prices). Staff can sign up; the admin approves them and chooses what each person may do. Every change is recorded in a history log that cannot be edited. **Waiting on KJS:** product list with photos, and the price policy.
