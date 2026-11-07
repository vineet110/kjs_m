# Session notes (Nishita)

One subheading per task. Moved into the shared docs after the PR merges (see `docs/prompt.md` section 7).


## Home page look and theme colours (feat/home-look, 5 Nov)

- Headings on the public site use Plus Jakarta Sans (`next/font/google`, part of Next, no new package). Scoped with the `site-public` class on `<main>` in the public layout, so the staff portal is unchanged.
- Banner row: a little taller, bigger headline, soft gold glow behind. Hyphenated words in the banner title ("Co-Manufacturing") no longer break at the hyphen.
- Tried making the pack photos float without their white cards (mix-blend-multiply); it looked worse, so it was put back.
- Dark stats box: added the item count (from the catalogue, a real number).
- Best sellers on a white band; "How it works" is now a dark band; "Recommended" got the gold heading line.
- Bottom enquiry box and the Koko chat window: forest green replaced by gold / charcoal to match the logo.
- Empty space under the category menu: a chocolate bars picture linking to Confectionery.
- Search hint no longer mentions item numbers (search by item number still works).
- Tea hidden on the home and products pages for now: `HIDDEN_CATEGORIES` in `lib/catalogue.ts`. Tea is still in the database and `/categories/tea` still opens directly.
- Still green elsewhere: hover colour on category names and a few other pages. Not changed yet.

## "Let's connect" WhatsApp popup (feat/connect-popup, 5 Nov)

- New `ConnectPopup.tsx`, added once in the public layout, so it works on every public page and never in the staff portal.
- Up to 3 popups per visit: 8 s after the visit starts, 30 s after the first is closed, 60 s after the second is closed. Fixed times, not random (asked for). Each wait starts when the previous popup is gone.
- The WhatsApp message is drafted from the open page: product name, category name, private label, partners, contact, or a general message for home.
- Desktop: a card in the middle. Phones: a bottom sheet. The page behind is blurred.
- Stops for the visit once someone clicks WhatsApp or asks for a quote. Never opens over the enquiry form. Its state is in `sessionStorage` (`kjs-connect`), so a reload doesn't restart it.
- Testing: a tab that already saw the popups won't show them again. Use a new or Incognito tab, or run `sessionStorage.removeItem('kjs-connect')` in the console.
- Switch: `connect_popup` in `config/features.ini` (also added to `FeaturesIni`). The frontend shows it unless the switch is `false`, so an older API without the field still works.
- `WhatsAppButton.tsx` now exports `WhatsAppIcon` so the popup reuses the same logo.
- Open question: Google can rank pages lower when popups cover phone pages; the bottom sheet is the gentler form. Watch Search Console after launch.
- Review fixes (5 Nov): the 10 s retry timer is now cancelled when leaving the page; `next` also moves on when a popup opens (a reload while it is open waits the full gap); the popup waits while the product quick view or an open Koko chat is on screen, not just the enquiry form; badly formed saved data is ignored instead of crashing the layout.

## Product cards grow 20% on hover (feat/card-hover, 5 Nov)

- Product cards (`ProductCard`, `HomeProductCard`) have a `hover-grow` class: under the cursor they grow 20% and come in front of their neighbours.
- Direction: a card at the left edge of its grid grows to the right, one at the right edge grows to the left, the middle ones grow evenly. `HoverGrowSides.tsx` (one `mouseover` listener in the public layout) measures this when the cursor enters, so it works on 2, 3 or 4 columns.
- Styles in `globals.css`, outside the Tailwind layers so they win over the cards' own hover lift. The grid cell is put on top with `:has()`, because the cards' `Reveal` wrappers would otherwise paint later cards over the grown one.
- Only with a mouse at tablet/desktop widths (`hover: hover` and 768px+). Phones: no effect. Reduced motion: no animation.

## Lead Management and User Creation Form (feat/lead-management, 6 Nov)

- New sidebar group "Lead Management": Contacts, Tasks (moved here from My work), Koko Lead, Internal lead. Same pages for admin and staff (`/employee/...`): `leads.view_all` sees everyone's leads, others their own + unassigned.
- Contacts = leads grouped per person (same last 10 phone digits, else same email). Table copies the LEMAI screenshot: S.No, Name, Email, Phone No, Converted Value, Active / In-Active Opportunities, Total, Actions. Active = new or contacted enquiries, In-Active = closed. Converted Value shows "—" (deal values are not recorded yet). Search and pages run in the browser (`DataTable.tsx`).
- Contact page (`/employee/contacts/<lead id>`): header (phone hidden until clicked), the person's other enquiries as chips, Lead Pipeline (our 3 stages New / Contacted / Closed; closing asks for an outcome), tabs Info / Notes / Task / Timeline / Proposals, quick actions Notes / Task / Lead Share. Removed as asked: the top-right buttons (AI, money, mic, Call, Communication), Call Logs, Meeting, Recording and Payments tabs, Last proposal sent, Meetings, Opportunities box, Engagement summary.
- Proposals tab is an empty "not recorded yet" box. Notes can be Note / Call / Email (a call or email still stops the respond timer).
- Internal lead: staff type it in ("+ Add lead"). Source `internal`, assigned to and created by that person. Guess to check with KJS: no consent tick box, the staff member's conversation with the buyer counts as consent.
- Tasks on a lead: `GET/POST /employee/leads/{id}/tasks`, saved as tasks with source `lead`, `source_ref` `lead:<id>`, so they also show on the Tasks page.
- Admin: new Users page (`/admin/users`) and User Creation Form (`/admin/users/new`, edit at `/admin/users/<id>`), with the live profile card on the right. Fields: name, email, phone, employee code, branch, role, reporting to, profile image. New accounts are active at once; the admin sees a one-time password once. Only an admin can give the admin role or edit existing accounts.
- Branch is free text with "Main Branch" suggested. Waiting for KJS's real branch list.
- Profile page: same card on the right; employee code, branch, role and reporting to are read-only there. Staff can change their own photo. Photos are files owned by `("user", id)`.
- New migration 0015 (users: employee_code, branch, reporting_to; leads: created_by). Tell Vineet before he adds a migration.
- New routes: `GET /employee/contacts`, `GET /employee/contacts/{lead_id}`, `POST /employee/leads`, `?source=` on both lead lists, `POST /admin/users`, `PATCH /admin/users/{id}`. Tests: `tests/test_lead_management.py` (14), full suite 194 passed.
- The "Let's connect" popup text change that was uncommitted on `preview/all` is in `git stash` ("ConnectPopup text change"), not in this branch.
