"""Koko sends the AI only the products that matter, and shows a catalogue card on product and category pages.
The AI is mocked (no real calls): `seen` records the system prompt Koko would have sent."""
import pytest

from app.core.database import AsyncSessionLocal
from app.seed_catalogue import add_catalogue
from app.services import catalog_service, koko_service, llm
from app.services.koko_service import PROMPT_LIMIT

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
    assert len(seen) == 3 and all(len(p) <= PROMPT_LIMIT for p in seen), [len(p) for p in seen]
    # Every category is still named, so Koko knows the whole range exists
    cats = (await client.get("/api/v1/public/categories")).json()
    assert all(f"- Category: {c['name']}" in seen[1] for c in cats)


async def test_prompt_stays_small_even_with_long_facts(client, catalogue, seen):
    """Admin > Koko facts can grow: then fewer products go in, the prompt still fits."""
    async with AsyncSessionLocal() as db:
        cats, prods = await catalog_service.list_categories(db), await catalog_service.list_products(db)
    long_facts = "KJS fact line about our factory.\n" * 200  # about 6,600 characters (today: about 2,700)
    cat = next(c for c in cats if c.slug == "confectionery")
    prompt = koko_service.build_prompt(long_facts, "wafers biscuits chocolate", cat, cats, prods)
    assert len(prompt) <= PROMPT_LIMIT and "- Product:" in prompt  # fewer products, but still some


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
