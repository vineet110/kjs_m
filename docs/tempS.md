# Session notes (Nishita)

One subheading per task. Moved into the shared docs after the PR merges (see `docs/prompt.md` section 7).



---------------------------------------------------------------------------------------------------

## Koko: send the right catalogue (branch feat/koko-catalogue, 9 Nov)

Plan: Vineet's "Koko: send the right catalogue…" (tempV.md). Cards in the chat, not a PDF (decided 9 Nov).

1. The bug: every message sent all 72 products (about 8,300 tokens); Groq's free tier allows 8,000 a minute,
   so every chat got "Sorry, I can't answer right now".

2. Fix (`koko_service.py`): the AI gets every category's name, the products of the page's category, and the
   products the question names (at most 15, 300 characters each). The prompt stays under 12,000 characters;
   if long Admin > Koko facts push it over, fewer products go in (and it logs `koko.prompt_too_long`).
   `llm.py` unchanged: it already logs the reason (413 / 429).

3. Card: on `/categories/<slug>` or `/products/<slug>` (with or without `/en`), Koko's first reply carries
   `catalogue` (category + up to 6 products) from the database. Also when the AI fails or today's budget is used.
   Confectionery shows its kinds (wafers, biscuits, …). Shown under the reply as cards with pictures and links.

4. Tests: new `backend/tests/test_koko_catalogue.py` (21: page paths, bad paths, first message only, AI down,
   budget used, size limit with the full catalogue and with long facts, coffee and wafer questions). Backend 280
   pass, frontend 44, e2e api 196 and browser 74 (new: "hi" on the coffee page shows the cards).

5. Real key, full catalogue (74 products) on the local test database: a wafer question on the home page, "hi" on
   Confectionery (with 6 cards) and a coffee and tea question all answered, three in one minute.

6. Assumptions (for backlog section 3): card on the first message only, up to 6 products; only on product and
   category pages; picked by page and keywords (embeddings later, when the facts outgrow this).

7. Seen, not changed: Koko sometimes answers with `**bold**` markdown, shown as stars (the chat shows plain text).
   The card shows the category's first 6 products by name (for Confectionery: mostly wafers).

8. PR #50 review fixes (all checked real first): the AI gets the viewed product, then the products the last 3
   visitor messages name, then the page's category (sales' picks first), max 8; the card puts the viewed product
   first, then best sellers / offers, one of each kind; card on Koko's first real reply (the widget no longer
   sends its own error and "thank you" lines); no database work once the budget is used and no card is due; any
   2-letter language prefix; plurals (-es, -ies); no markdown in replies. Prompt now about 2,000 tokens.
   Tests: Koko 32, backend 291, frontend 44, e2e api 196, browser 74. Real key, full catalogue: 5 chats in one minute.

9. For Vineet / KJS: Groq's free tier (8,000 tokens a minute for the whole site) fits only a few Koko messages a
   minute. A paid tier before real traffic.
