# Session notes (Vineet)

One subheading per task. Moved into the shared docs after the PR merges (see `docs/prompt.md` section 7).

## 19 Nov 2026: Home page refresh, PR A (look and motion), branch feat/site-ui, draft PR #103

### What was planned

1. Four PRs: A (look and motion), B1 (admin hero slides and stats), B2 (admin partners with logos, activity
   lines), C (the site talks: hover messages, offer box, pop-ups, offer form).
2. Approved mockup: v4 artifact (claude.ai/artifact/AbUCSYbhTk53czrC8R1SXA).

### Done in PR A

1. `config/site_ui.ini` + `SiteUiIni`, shared in `/public/config` as `site_ui` (display settings only).
   Frontend reads it with `siteUi()`; fallback is the old look.
2. Hero: 3px gold-and-charcoal striped line; it drives the slides (no drift on hover). Slide time from ini.
3. Home cards and tiles come in from the left (`Reveal from="left"`). Products page unchanged.
4. How it works: steps light up 1 to 4 (`StepsLightUp`).
5. Partner strip slides in a loop and is never empty (`PartnerStrip`). Dr. Reddy's added (confirmed by Vineet).
6. Soft glow ring on Ask Koko and WhatsApp (`.glow-ring`).
7. Dark mode on every website page: sun/moon button, choice remembered, no white flash. Colours from one map
   in `globals.css` scoped to `.site-shell` (staff portal never dark). `.keep-light` keeps light blocks light.
8. Top strip above the header (since 2020, certificates, phone, email), scrolls away.
9. `enabled = false` in site_ui.ini brings back the old home page.

### Decisions (19 Nov)

1. Dark mode inside PR A, on all website pages (colours only).
2. Keep the dark header. Keep the old "Let's connect" popup next to the new offer box (PR C).
3. Products page: no change. Home cards: left-to-right entrance, 20% hover grow stays.
4. Default theme is light; `dark_follows_system = false` (Vineet can switch it on in the ini).
5. Pillow approved for PR B1 (compress uploaded images).
6. English only for now (site is English at launch, backlog D2); tables built so a language field can be added.
7. Offer-form leads tagged "website offer", need consent text + quick T&C and the hidden anti-spam field.

### Guesses to log in backlog §3 when folding

1. Pop-up times are counted from page load: 5, 8, 11, 15, 17, 25 s, then the cycle repeats (30, 33, ...).
2. Offer form auto-closes after 14 s untouched, warning 4 s before. Max 20 pop-ups per visit, 1 at a time on phones.
3. Partner logo files: from Vineet's folder (seeklogo copies); partners' OK confirmed by Vineet.
   Extras in the folder (Nestlé Health Science, CCL) not shown until Vineet says so.

### Checks

1. Backend config tests pass; frontend typecheck, 75 tests and build pass.
2. One live check (local API on the test database): light and dark home page, products page, connect popup.
   Test database has no products, so product cards in dark mode are not yet seen.

### New terms for kb.md

1. site-shell: the website's outer box; dark-mode colours apply only inside it.
2. keep-light: a class for blocks that stay light in dark mode.
