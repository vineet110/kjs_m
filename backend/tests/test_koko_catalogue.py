"""Koko sends the AI only the products that matter, and shows a catalogue card on product and category pages.
The AI is mocked (no real calls): `seen` records the system prompt Koko would have sent."""
import pytest

from app.core.database import AsyncSessionLocal
from app.seed_catalogue import add_catalogue
from app.services import catalog_service, koko_service, llm
from app.core.config.ini import cfg

HDR = {"x-requested-with": "kjs"}
CHAT = "/api/v1/koko/chat"


@pytest.fixture
async def catalogue():
    """The real KJS catalogue (72 products), as on the live site."""
    async with AsyncSessionLocal() as db:
        await add_catalogue(db)


@pytest.fixture
def seen(monkeypatch):
    """Mock the AI: record each system prompt, answer "OK"."""
    prompts: list[str] = []

    async def fake_chat(system, messages, max_tokens=None):
        prompts.append(system)
        return "OK"
    monkeypatch.setattr(llm, "chat", fake_chat)
    return prompts


def ask(text: str, page: str = "", before: list | None = None) -> dict:
    return {"messages": [*(before or []), {"role": "user", "content": text}], "page": page}


async def a_product(client, category: str) -> dict:
    return next(p for p in (await client.get("/api/v1/public/products")).json() if p["category_slug"] == category)


async def test_category_page_first_hi_gets_the_card(client, catalogue, seen):
    r = (await client.post(CHAT, json=ask("hi", "/categories/wafers"), headers=HDR)).json()
    card = r["catalogue"]
    assert r["reply"] == "OK" and card["category_slug"] == "wafers" and card["category_name"] == "Wafers"
    assert 1 <= len(card["products"]) <= 6
    assert all(p["slug"] and p["name"] and "image_path" in p for p in card["products"])
    # The AI was told about this category's products
    assert card["products"][0]["name"] in seen[0]


async def test_product_page_uses_the_products_category_with_or_without_locale(client, catalogue, seen):
    p = await a_product(client, "biscuits")
    for page in (f"/products/{p['slug']}", f"/en/products/{p['slug']}", f"/en/products/{p['slug']}?x=1#top"):
        r = (await client.post(CHAT, json=ask("hi", page), headers=HDR)).json()
        assert r["catalogue"]["category_slug"] == "biscuits", page


@pytest.mark.parametrize("page", ["", "/", "/en", "/contact", "/products", "/categories/no-such-thing",
                                  "/products/no-such-product", "/categories/wafers/extra", "///", "../../etc/passwd"])
async def test_other_or_bad_pages_get_no_card_and_no_error(client, catalogue, seen, page):
    r = await client.post(CHAT, json=ask("hi", page), headers=HDR)
    assert r.status_code == 200 and r.json()["catalogue"] is None


async def test_card_only_on_the_first_message(client, catalogue, seen):
    before = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "Hello!"}]
    r = (await client.post(CHAT, json=ask("and wafers?", "/categories/wafers", before), headers=HDR)).json()
    assert r["catalogue"] is None


async def test_parent_category_card_shows_its_kinds(client, catalogue, seen):
    # Confectionery is made of chocolate bars, wafers, biscuits, marshmallow & cakes
    card = (await client.post(CHAT, json=ask("hi", "/categories/confectionery"), headers=HDR)).json()["catalogue"]
    assert card["category_slug"] == "confectionery" and len(card["products"]) == 6


async def test_card_still_sent_when_the_ai_fails(client, catalogue, monkeypatch):
    async def down(*a, **k):
        raise llm.LLMUnavailable("413 Request too large")
    monkeypatch.setattr(llm, "chat", down)
    r = (await client.post(CHAT, json=ask("hi", "/categories/wafers"), headers=HDR)).json()
    assert r["reply"] == koko_service.FALLBACK and r["catalogue"]["category_slug"] == "wafers"


async def test_card_still_sent_when_todays_ai_budget_is_used_up(client, catalogue, seen, monkeypatch):
    monkeypatch.setattr(koko_service, "_within_daily_budget", lambda: False)
    r = (await client.post(CHAT, json=ask("hi", "/categories/wafers"), headers=HDR)).json()
    assert r["reply"] == koko_service.FALLBACK and r["catalogue"]["category_slug"] == "wafers" and not seen


async def test_prompt_stays_small_with_the_whole_catalogue(client, catalogue, seen):
    """The bug: all 72 products went to the AI (about 8,300 tokens, over Groq's 8,000 a minute)."""
    products = (await client.get("/api/v1/public/products")).json()
    assert len(products) > 50  # really the full catalogue
    for page, question in (("/categories/confectionery", "hi"), ("/", "coffee tea wafers biscuits chocolate cakes"),
                           (f"/products/{products[0]['slug']}", "Do you make private label sticks?")):
        await client.post(CHAT, json=ask(question, page), headers=HDR)
    assert len(seen) == 3 and all(len(p) <= cfg().koko.prompt_limit for p in seen), [len(p) for p in seen]
    # Every category is still named, so Koko knows the whole range exists
    cats = (await client.get("/api/v1/public/categories")).json()
    assert all(f"- Category: {c['name']}" in seen[1] for c in cats)


async def test_prompt_stays_small_even_with_long_facts(client, catalogue, seen):
    """Admin > Koko facts can grow: then fewer products go in, the prompt still fits."""
    async with AsyncSessionLocal() as db:
        cats, prods = await catalog_service.list_categories(db), await catalog_service.list_products(db)
    long_facts = "KJS fact line about our factory.\n" * 125  # about 4,100 characters (today: about 2,700)
    cat = next(c for c in cats if c.slug == "confectionery")
    prompt = koko_service.build_prompt(long_facts, ["wafers biscuits chocolate"], cat, cats, prods)
    assert len(prompt) <= cfg().koko.prompt_limit and "- Product:" in prompt  # fewer products, but still some


async def test_coffee_question_on_the_home_page_gets_the_coffee_products(client, catalogue, seen):
    coffee = [p["name"] for p in (await client.get("/api/v1/public/products?category=coffee")).json()]
    r = (await client.post(CHAT, json=ask("What coffee do you make?", "/"), headers=HDR)).json()
    assert r["catalogue"] is None  # no card on the home page
    assert coffee and all(name in seen[0] for name in coffee)


async def test_wafer_question_names_wafers_not_everything(client, catalogue, seen):
    await client.post(CHAT, json=ask("Do you have wafers?", "/"), headers=HDR)
    wafers = [p["name"] for p in (await client.get("/api/v1/public/products?category=wafers")).json()]
    coffee = [p["name"] for p in (await client.get("/api/v1/public/products?category=coffee")).json()]
    assert any(w in seen[0] for w in wafers)
    assert not any(c in seen[0] for c in coffee)  # not the whole catalogue


def test_page_paths_never_raise():
    for page in ("", "/", "//", "/en/", "/en/categories", "%%%", "/categories/" + "a" * 500, "?", "#"):
        assert koko_service.page_category(page, [], []) is None


# ---------- Review fixes (PR #50) ----------

async def products_of(client, category: str) -> list[dict]:
    return (await client.get(f"/api/v1/public/products?category={category}")).json()


async def test_asked_for_products_come_before_the_pages_category(client, catalogue, seen):
    """Review 1: "instant coffee?" on the Confectionery page (58 products) used to send no coffee at all."""
    coffee = [p["name"] for p in await products_of(client, "coffee")]
    await client.post(CHAT, json=ask("Do you make instant coffee?", "/categories/confectionery"), headers=HDR)
    assert coffee and all(name in seen[0] for name in coffee)


async def test_follow_up_questions_keep_their_products(client, catalogue, seen):
    """Review 2: "and the pack sizes?" after a coffee question used to send no products."""
    before = [{"role": "user", "content": "What coffee do you make?"}, {"role": "assistant", "content": "We make..."}]
    await client.post(CHAT, json=ask("and the pack sizes?", "/", before), headers=HDR)
    coffee = [p["name"] for p in await products_of(client, "coffee")]
    assert all(name in seen[0] for name in coffee)


async def test_the_viewed_product_is_always_sent_and_first_on_the_card(client, catalogue, seen):
    """Review 3: on a product page in a big category, that product could be left out of both."""
    confectionery = await products_of(client, "confectionery")
    last = sorted(confectionery, key=lambda p: p["name"])[-1]  # the one that used to fall off
    r = (await client.post(CHAT, json=ask("hi", f"/products/{last['slug']}"), headers=HDR)).json()
    assert last["name"] in seen[0]
    assert r["catalogue"]["products"][0]["slug"] == last["slug"]


async def test_card_after_a_failed_first_try(client, catalogue, seen):
    """Review 4: "hi" timed out (the widget keeps its error line to itself), the visitor asks again: still the card."""
    before = [{"role": "user", "content": "hi"}]  # no Koko reply in between: it never arrived
    r = (await client.post(CHAT, json=ask("hello?", "/categories/wafers", before), headers=HDR)).json()
    assert r["catalogue"]["category_slug"] == "wafers"


async def test_card_mixes_kinds_and_puts_sales_picks_first(client, catalogue, seen):
    """Smaller 1: the Confectionery card was all wafers. Best sellers and offers first, then one of each kind."""
    from sqlalchemy import update
    from app.models.catalog import Product
    biscuit = (await products_of(client, "biscuits"))[-1]
    async with AsyncSessionLocal() as db:
        await db.execute(update(Product).where(Product.slug == biscuit["slug"]).values(is_best_seller=True))
        await db.commit()
    card = (await client.post(CHAT, json=ask("hi", "/categories/confectionery"), headers=HDR)).json()["catalogue"]
    on_card = {c["slug"] for c in card["products"]}
    kinds = {p["category_slug"] for p in await products_of(client, "confectionery") if p["slug"] in on_card}
    assert card["products"][0]["slug"] == biscuit["slug"]  # the best seller first
    assert len(kinds) == 4  # wafers, biscuits, bars, cakes: all on the card


async def test_no_database_work_once_the_budget_is_used_and_no_card_is_due(client, catalogue, monkeypatch):
    """Smaller 2: later messages after today's budget is used: answered without loading the catalogue."""
    monkeypatch.setattr(koko_service, "_within_daily_budget", lambda: False)

    async def boom(*a, **k):
        raise AssertionError("the catalogue should not be loaded")
    monkeypatch.setattr(catalog_service, "list_products", boom)
    before = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "Hello!"}]
    r = (await client.post(CHAT, json=ask("wafers?", "/categories/wafers", before), headers=HDR)).json()
    assert r["reply"] == koko_service.FALLBACK and r["catalogue"] is None


@pytest.mark.parametrize("page", ["/hi/categories/wafers", "/ar/categories/wafers", "/en/categories/wafers"])
async def test_any_language_prefix_still_gets_the_card(client, catalogue, seen, page):
    """Smaller 4: adding Hindi or Arabic later must not silently drop the card."""
    r = (await client.post(CHAT, json=ask("hi", page), headers=HDR)).json()
    assert r["catalogue"]["category_slug"] == "wafers"


def test_plurals_match_the_singular():
    """Smaller 5: only a trailing "s" was dropped, so "pouches" or "boxes" never matched."""
    words = koko_service._words("Pouches, boxes, varieties, wafers, glass")
    assert {"pouch", "box", "variety", "wafer", "glass"} <= words


async def test_prompt_asks_for_plain_text_and_stays_small(client, catalogue, seen):
    """Koko's **bold** showed as stars; and the prompt is now about half, so more chats fit in Groq's minute."""
    await client.post(CHAT, json=ask("chocolate wafers biscuits coffee tea cakes", "/categories/confectionery"), headers=HDR)
    assert "no markdown" in seen[0] and len(seen[0]) <= 8_000


async def _koko_prompt(facts: str = "") -> str:
    async with AsyncSessionLocal() as db:
        cats, prods = await catalog_service.list_categories(db), await catalog_service.list_products(db)
    return koko_service.build_prompt(facts, ["hello"], None, cats, prods)


async def _coffee_only():
    """Switch every other category off; gives back the ids it switched off (to switch only those back on)."""
    from sqlalchemy import select, update
    from app.models.catalog import Category
    async with AsyncSessionLocal() as db:
        ids = list((await db.scalars(select(Category.id).where(Category.slug != "coffee", Category.is_active))).all())
        await db.execute(update(Category).where(Category.id.in_(ids)).values(is_active=False))
        await db.commit()
    return ids


async def _switch_back_on(ids):
    from sqlalchemy import update
    from app.models.catalog import Category
    async with AsyncSessionLocal() as db:
        await db.execute(update(Category).where(Category.id.in_(ids)).values(is_active=True))
        await db.commit()


def _intro(prompt: str) -> str:
    """Koko's own description of KJS: the text before the facts."""
    return prompt.split("KJS FACTS:")[0]


async def test_koko_names_only_the_categories_shown(client, catalogue):
    """Coffee-only (Admin > Products: the rest hidden): Koko's own description of KJS names coffee only, and
    the full range again once everything is shown. Categories are switched back even if an assert fails."""
    ids = await _coffee_only()
    try:
        intro = _intro(await _koko_prompt())
        assert "(coffee; private label" in intro and "confectionery" not in intro.lower()
    finally:
        await _switch_back_on(ids)
    assert "confectionery" in _intro(await _koko_prompt())


async def test_koko_facts_product_areas_follow_the_switches(client, catalogue):
    """The facts (kjs_facts.md or Admin > Koko) say {product_areas}: Koko gets the categories shown."""
    from app.services.content_service import KOKO_FACTS_FILE
    facts = KOKO_FACTS_FILE.read_text(encoding="utf-8")
    assert "{product_areas}" in facts  # the default facts use it
    ids = await _coffee_only()
    try:
        prompt = await _koko_prompt(facts)
        assert "Product areas: coffee." in prompt and "{product_areas}" not in prompt
    finally:
        await _switch_back_on(ids)
    areas = _areas_line(await _koko_prompt(facts))
    assert "coffee" in areas and "confectionery" in areas  # all shown again (any order)


def _areas_line(prompt: str) -> str:
    return next(line for line in prompt.splitlines() if line.startswith("- Product areas:")).lower()


async def test_facts_saved_in_admin_with_the_old_areas_line_follow_too(client, catalogue):
    """Facts saved in Admin > Koko before {product_areas} existed still list every area: that exact old list
    is swapped for the categories shown, the rest of the facts stays as written."""
    old = "- Product areas: coffee, tea, health drinks and confectionery. We sell B2B only.\n- Our own fact."
    ids = await _coffee_only()
    try:
        prompt = await _koko_prompt(old)
        assert _areas_line(prompt) == "- product areas: coffee. we sell b2b only." and "- Our own fact." in prompt
    finally:
        await _switch_back_on(ids)
