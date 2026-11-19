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

## 19 Nov 2026: Home page refresh, PRs B1, B2, C (stacked on PR A #103)

Branches and PRs: feat/site-ui-b1 (#104, base feat/site-ui), feat/site-ui-b2 (#105, base b1),
feat/site-ui-c (#106, base b2). Merge in order A, B1, B2, C; retarget each to main after the one below merges.

### B1: Admin edits the hero (#104)

1. hero_slides, hero_stats (migration 0032). Admin > Website > Home banner. Public GET /public/hero.
2. Pictures: file owner website/hero, shrunk with Pillow (new dependency, approved) to image_max_px, upright,
   GPS/camera data removed. A picture deleted on the Files page drops out of the slide.
3. Stat numbers count up from 0 (missed in PR A, added here).
4. Left out on purpose: the mockup's badge and highlighted word (the real hero has no such parts).

### B2: Partner logos and pop-up activity (#105)

1. brand_partners, activity_lines (migration 0033). Admin > Website > Partner logos, Pop-up activity.
2. Public /public/brand-partners (not /public/partners: that is the partner application form) and /public/activity.
3. Activity needs a real time (not in the future); older than activity_max_age_days hides itself.
4. Upload-ready logos (Nestlé, Unilever, Mayora, Dr. Reddy's): Downloads/kjs-partner-logos-ready. Upload them
   in Admin > Website > Partner logos after deploy (they go to R2 through the normal upload).

### C: The site talks (#106)

1. Lead source website_offer: phone + consent, name optional (saved as "Website visitor (offer form)").
   Refused when offer_box is off.
2. One speech bubble (hover/focus) + nudges once per visit; typing search; Get your offer box with pop-ups at
   popup_times from page load, stacked, capped per visit; phone-first form with quick T&C and hidden anti-spam
   field; auto-close with warning; never while in use.
3. Home page only (talk_all_pages = false). Texts in Admin > Text & SEO (talk.*, offer.*).
4. Old "Let's connect" popup kept (decision); the talk layer pauses while any popup window is open.

### Review findings left on purpose (small)

1. Hero and showcase settings share site_ui.ini instead of their own ini files.
2. Two editors switching on at the same moment can pass the on-limit by one.
3. Replaced pictures and logos stay in storage (unused, public).
4. A few animation timings and the 10-15 digit phone check are fixed in the frontend code.

### Checks

1. Full backend run 593 passed; frontend typecheck, 78 tests, build.
2. Live checks per PR on a local API (test database): admin slide + count-up, logos in the strip, pop-up
   timing, form open/send/auto-close, lead saved as website_offer, hover bubble, typing search.

### After merging (all four)

1. alembic upgrade head (0032, 0033). pip install -r requirements.txt (Pillow).
2. Copy config/site_ui.ini to the VPS config folder.

### New terms for kb.md

1. Stacked PRs: each PR's base is the one below it, so each diff shows only its own change.
2. website_offer: lead source of the Get your offer form.
