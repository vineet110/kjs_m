# Session notes (Nishita)

One subheading per task. Moved into the shared docs after the PR merges (see `docs/prompt.md` section 7).


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
