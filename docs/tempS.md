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
