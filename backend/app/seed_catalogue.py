"""Products from the KJS product catalogue PDF ("KJS INDIA products.pdf", received 27 Oct 2026).

Run:  python -m app.seed_catalogue      (from the backend/ folder, after `python -m app.seed`)

Safe to run many times: a product is added only if its slug is new,
so edits made later in Admin > Products are never overwritten.

One row per product family. The item numbers, weights and pack sizes go into the description
(the product page shows it line by line); `pack_formats` keeps a short summary for the cards.
Pictures were cut out of the catalogue pages: frontend/public/images/products/<slug>.jpg.
No prices and no MOQ: the catalogue has neither (MOQ shows "On request").

BEVERAGES: coffees and instant drink powders from the coffee catalogue ("products (1).pdf", 4 Nov 2026),
added to the original Coffee / Health drinks categories and a new Instant drink powders one.
"""
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.catalog import Category, Product

# slug, name, description, sort order. Added next to the original four categories.
CATALOGUE_CATEGORIES = [
    ("chocolate-bars", "Chocolate bars", "Compound chocolate coated bars with nougat, caramel, peanut or coconut filling.", 5),
    ("wafers", "Wafers", "Cream-filled wafers: chocolate coated, crispy, big-size and multi-flavour packs.", 6),
    ("marshmallow-cakes", "Marshmallow & cakes", "Chocolate coated marshmallow sandwich biscuits and cocoa cakes.", 7),
    ("biscuits", "Biscuits", "Sandwich biscuits, Petit Beurre, Maria, sesame and finger biscuits, single packs to family packs.", 8),
    ("instant-drinks", "Instant drink powders", "Instant fruit drink powders: lime, mango, orange, strawberry and more.", 9),
]

BAR = "Compound chocolate coated bar with nougat and caramel."

# Each item: (item no, variant, net weight, pieces per box, boxes per case). Variant "" = only one.
PRODUCTS = [
    # ---------- Chocolate bars (catalogue page 1) ----------
    dict(slug="pacho-chocolate-bar", name="Pacho chocolate bar", cat="chocolate-bars", text=BAR,
         items=[("801", "", "25 g", 24, 6)]),
    dict(slug="paleyo-chocolate-bar", name="Paleyo chocolate bar", cat="chocolate-bars", text=BAR,
         items=[("802", "", "25 g", 24, 6)]),
    dict(slug="philo-chocolate-bar", name="Philo chocolate bar", cat="chocolate-bars", text=BAR,
         items=[("803", "", "25 g", 24, 6)]),
    dict(slug="banchetto-chocolate-bar", name="Banchetto chocolate bar", cat="chocolate-bars", text=BAR,
         items=[("804", "", "40 g", 24, 6)]),
    dict(slug="grandy-chocolate-bar", name="Grandy chocolate bar", cat="chocolate-bars",
         text="Compound chocolate coated bar with nougat, caramel and peanut.",
         items=[("805", "", "40 g", 24, 6)]),
    dict(slug="ranch-chocolate-bar", name="Ranch chocolate bar", cat="chocolate-bars", text=BAR,
         items=[("806", "", "40 g", 24, 6)]),
    dict(slug="cocolay-coconut-bar", name="Cocolay coconut bar", cat="chocolate-bars",
         text="Milky compound chocolate coated bar with coconut filling.",
         items=[("808", "", "25 g", 24, 6), ("809", "", "10 g", 24, 12)]),

    # ---------- Wafers ----------
    dict(slug="gofrey-crispy-x2", name="Gofrey Crispy X2", cat="wafers",
         text="Double wafer bar coated with compound chocolate, filled with cream and rice crunches.",
         items=[("643", "Cocoa cream", "60 g", 24, 6), ("644", "Orange flavoured cream", "60 g", 24, 6)]),
    dict(slug="share-wafer", name="Share wafer", cat="wafers",
         text="Compound chocolate coated cocoa cream wafers, made to eat and share.",
         items=[("625", "", "60 g", 24, 6)]),
    dict(slug="hello-coconut-wafer", name="Hello Coconut wafer", cat="wafers",
         text="Coconut and cocoa coated wafers with cocoa cream.",
         items=[("635", "", "40 g", 24, 6)]),
    dict(slug="gofrey-crispy", name="Gofrey Crispy", cat="wafers",
         text="Wafers coated with compound chocolate and rice crispies.",
         items=[("646B", "Cocoa cream", "27 g", 24, 6), ("647B", "Orange flavoured cream", "27 g", 24, 6)]),
    dict(slug="gofrey-hazelnut", name="Gofrey Hazelnut", cat="wafers",
         text="Hazelnut and compound chocolate coated wafer with cocoa cream.",
         items=[("605", "", "32 g", 24, 6), ("605A", "", "27 g", 24, 6)]),
    dict(slug="gofrey-cocoa", name="Gofrey Cocoa", cat="wafers",
         text="Compound chocolate coated wafer with cocoa cream.",
         items=[("600", "", "30 g", 24, 6), ("600A", "", "28 g", 24, 6), ("600B", "", "32 g", 24, 6), ("600C", "", "35 g", 24, 6)]),
    dict(slug="gofrey-milk", name="Gofrey Milk", cat="wafers",
         text="White compound chocolate coated wafer with cocoa cream.",
         items=[("610", "", "30 g", 24, 6), ("610A", "", "32 g", 24, 6), ("610B", "", "35 g", 24, 6), ("610C", "", "28 g", 24, 6)]),
    dict(slug="gofrey-black-white", name="Gofrey Black & White", cat="wafers",
         text="Cocoa and white compound chocolate coated wafer with cocoa cream.",
         items=[("620", "", "30 g", 24, 6), ("620A", "", "28 g", 24, 6), ("620B", "", "32 g", 24, 6)]),
    dict(slug="hadiye-cocoa", name="Hadiye Cocoa", cat="wafers",
         text="Compound chocolate coated wafer with cocoa cream.",
         items=[("601", "", "22–25 g", 24, 6)]),
    dict(slug="hadiye-milk", name="Hadiye Milk", cat="wafers",
         text="White compound chocolate coated wafer with cocoa cream.",
         items=[("611", "", "22–25 g", 24, 6)]),
    dict(slug="maxi-big-wafers-chocolate", name="Maxi Big Wafers chocolate coated", cat="wafers",
         text="Big-size compound chocolate coated cocoa cream wafer.",
         items=[("612", "", "75 g", 24, 6)]),
    dict(slug="maxi-big-wafers-granule", name="Maxi Big Wafers coloured granule", cat="wafers",
         text="Big-size white compound chocolate coated wafer with coloured granules and cocoa cream.",
         items=[("613", "", "75 g", 24, 6)]),
    dict(slug="wafer-2021-chocolate", name="2021 Chocolate wafer", cat="wafers",
         text="Compound chocolate coated cocoa cream wafer.",
         items=[("676", "", "40 g", 24, 6)]),
    dict(slug="wafer-2021-milk", name="2021 Milk wafer", cat="wafers",
         text="White compound chocolate coated wafer with coloured granules and cocoa cream.",
         items=[("677", "", "40 g", 24, 6)]),
    dict(slug="first-dark-wafers", name="1st Dark Wafers", cat="wafers",
         text="Bitter compound chocolate coated cocoa cream wafers.",
         items=[("678", "", "70 g", 24, 6)]),
    dict(slug="dark-wafer", name="Dark Wafer", cat="wafers",
         text="Bitter compound chocolate coated cocoa cream wafer.",
         items=[("621", "", "40 g", 24, 6)]),
    dict(slug="black-wafer", name="Black Wafer", cat="wafers",
         text="Bitter compound chocolate coated cocoa cream wafer.",
         items=[("622", "", "30 g", 24, 6)]),
    dict(slug="milk-wafer", name="Milk Wafer", cat="wafers",
         text="White compound chocolate coated cocoa cream wafer.",
         items=[("623", "", "30 g", 24, 6)]),
    dict(slug="extreme4-dark", name="Extreme4 Dark", cat="wafers",
         text="Dark compound chocolate coated wafer with cocoa cream.",
         items=[("615", "", "45 g", 24, 6)]),
    dict(slug="extreme4-white", name="Extreme4 White", cat="wafers",
         text="White compound chocolate coated wafer with cocoa cream.",
         items=[("616", "", "45 g", 24, 6)]),
    dict(slug="brandon-dark", name="Brandon Dark", cat="wafers",
         text="Twin-bar dark compound chocolate coated wafer with cocoa cream.",
         items=[("691", "", "80 g", 24, 6)]),
    dict(slug="brandon-white", name="Brandon White", cat="wafers",
         text="Twin-bar white compound chocolate coated wafer with cocoa cream.",
         items=[("692", "", "80 g", 24, 6)]),
    dict(slug="maxi-cream-wafers", name="Maxi cream wafers", cat="wafers",
         text="Cream-filled wafers in three flavours (Summer Edition packs).",
         items=[("665", "Cocoa cream", "45 g", 24, 6), ("666", "Coconut cream", "45 g", 24, 6), ("667", "Coffee cream", "45 g", 24, 6)]),
    dict(slug="wafer-time", name="Wafer Time", cat="wafers",
         text="Cream-filled wafers in four flavours.",
         items=[("695", "Cocoa cream", "45 g", 24, 1), ("696", "Hazelnut flavoured cream", "45 g", 24, 1),
                ("697", "Vanilla cream", "45 g", 24, 1), ("698", "Coffee flavoured cream", "45 g", 24, 1)]),
    dict(slug="pacho-fret", name="Pacho Fret wafers", cat="wafers",
         text="Cream-filled wafers in vanilla, strawberry, banana and cocoa.",
         items=[("660", "Vanilla flavoured cream", "40 g", 24, 6), ("661", "Strawberry flavoured cream", "40 g", 24, 6),
                # 663 and 664 are both cocoa, in two pack designs (catalogue page 30: red and brown)
                ("662", "Banana flavoured cream", "40 g", 24, 6), ("663", "Cocoa cream, red pack", "40 g", 24, 6),
                ("664", "Cocoa cream, brown pack", "40 g", 24, 6)]),
    dict(slug="flavoured-wafers-35g", name="Flavoured wafers 35 g", cat="wafers",
         text="Cream-filled wafers in pistachio, orange, vanilla and cocoa.",
         items=[("670", "Pistachio flavoured cream", "35 g", 24, 6), ("671", "Orange flavoured cream", "35 g", 24, 6),
                ("672", "Vanilla flavoured cream", "35 g", 24, 6), ("673", "Cocoa cream", "35 g", 24, 6)]),
    dict(slug="palmix-x2-wafer", name="PalMix X2 wafer", cat="wafers",
         text="Double-layer cream wafers in four flavours.",
         items=[("680", "Vanilla flavoured cream", "80 g", 24, 6), ("681", "Orange flavoured cream", "80 g", 24, 6),
                ("682", "Pistachio flavoured cream", "80 g", 24, 6), ("683", "Cocoa cream", "80 g", 24, 6)]),
    dict(slug="extreme-extra-wafer", name="Extreme Extra wafer", cat="wafers",
         text="Cocoa cream wafer.",
         items=[("626", "", "60 g", 24, 6)]),
    dict(slug="gofrey-cocoa-cream-wafer", name="Gofrey cocoa cream wafer", cat="wafers",
         text="Wafers with cocoa cream, small single-serve pack.",
         items=[("675", "", "20 g", 30, 12)]),

    # ---------- Marshmallow & cakes ----------
    dict(slug="keky-latte", name="Keky Latte cake", cat="marshmallow-cakes",
         text="Compound chocolate coated cocoa cake with chocolate sauce.",
         items=[("500", "", "30 g", 24, 6), ("501", "", "30 g", 24, 6), ("502", "", "30 g", 24, 6)]),
    dict(slug="marshmallow-sandwich-biscuit", name="Marshmallow sandwich biscuit", cat="marshmallow-cakes",
         text="Marshmallow sandwich biscuit with chocolate or banana flavoured coating.",
         items=[("706", "Chocolate coating", "25 g", 24, 6), ("707", "Banana flavoured coating", "25 g", 24, 6)]),
    dict(slug="pacho-mellow", name="Pacho Mellow", cat="marshmallow-cakes",
         text="Compound chocolate coated marshmallow sandwich biscuit, three pack designs.",
         items=[("702", "", "25 g", 24, 6), ("702A", "", "20 g", 24, 6), ("702B", "", "22 g", 24, 6),
                ("703", "", "25 g", 24, 6), ("703A", "", "20 g", 24, 6), ("703B", "", "22 g", 24, 6),
                ("704", "", "25 g", 24, 6), ("704A", "", "20 g", 24, 6), ("704B", "", "22 g", 24, 6)]),
    dict(slug="pacho-mellow-banana", name="Pacho Mellow Banana", cat="marshmallow-cakes",
         text="Marshmallow sandwich biscuits with banana flavoured coating.",
         items=[("710", "", "22 g", 36, 12), ("710A", "", "20 g", 36, 12), ("712", "", "25 g", 30, 12),
                ("711", "", "14 g", 36, 12), ("711A", "", "12 g", 36, 12)]),
    dict(slug="marshmoe-sandwich-biscuits", name="MarshMoe sandwich biscuits", cat="marshmallow-cakes",
         text="Coated marshmallow cocoa sandwich biscuits, two per pack.",
         items=[("775", "Chocolate coating", "40 g", 24, 6), ("776", "White coating", "40 g", 24, 6)]),
    dict(slug="ranch-marshmallow-sandwich", name="Ranch marshmallow sandwich", cat="marshmallow-cakes",
         text="Bitter chocolate coated marshmallow cocoa sandwich biscuit.",
         items=[("772", "", "35 g", 24, 6)]),
    dict(slug="lupita-duble", name="Lupita Duble", cat="marshmallow-cakes",
         text="Coated marshmallow sandwich biscuits.",
         items=[("770A", "Chocolate coating", "47 g", 24, 6), ("771A", "Banana coating", "47 g", 24, 6)]),
    dict(slug="bigy-mellow", name="Bigy Mellow", cat="marshmallow-cakes",
         text="Chocolate and coconut coated marshmallow sandwich biscuit in four flavours.",
         items=[("760", "Chocolate & coconut", "56 g", 24, 6), ("760A", "Chocolate & coconut", "64 g", 24, 6),
                ("761", "White chocolate & coconut", "56 g", 24, 6), ("761A", "White chocolate & coconut", "64 g", 24, 6),
                ("762", "Banana flavoured", "56 g", 24, 6), ("762A", "Banana flavoured", "64 g", 24, 6),
                ("763", "Strawberry flavoured", "56 g", 24, 6), ("763A", "Strawberry flavoured", "64 g", 24, 6)]),
    dict(slug="sandwich-marshmallow-biscuit", name="Sandwich marshmallow biscuit", cat="marshmallow-cakes",
         text="Compound chocolate and coconut coated marshmallow sandwich biscuit in four flavours.",
         items=[("740", "Cocoa", "45 g", 24, 6), ("741", "White cocoa (milky)", "45 g", 24, 6),
                ("742", "Banana", "45 g", 24, 6), ("743", "Strawberry", "45 g", 24, 6)]),

    # ---------- Biscuits ----------
    dict(slug="kremali-sandwich-biscuits", name="Kremalı sandwich biscuits", cat="biscuits",
         text="Cream sandwich biscuits in vanilla, strawberry, banana, cocoa and caramel.",
         items=[("305", "Vanilla", "65 g", 24, 1), ("305A", "Vanilla", "65 g", 24, 6),
                ("306", "Strawberry", "65 g", 24, 1), ("306A", "Strawberry", "65 g", 24, 6),
                ("307", "Banana", "65 g", 24, 1), ("307A", "Banana", "65 g", 24, 6),
                ("308", "Cocoa biscuit, vanilla cream", "65 g", 24, 1), ("308A", "Cocoa biscuit, vanilla cream", "65 g", 24, 6),
                ("316", "Cocoa cream", "60 g", 24, 6), ("317", "Caramel flavoured cream", "60 g", 24, 6)]),
    dict(slug="fundo-sandwich-biscuits", name="Fundo sandwich biscuits", cat="biscuits",
         text="Ring sandwich biscuits with flavoured cream.",
         items=[("301", "Vanilla cream", "40 g", 24, 6), ("302", "Strawberry cream", "40 g", 24, 6),
                ("303", "Banana cream", "40 g", 24, 6), ("304", "Cocoa biscuit, vanilla cream", "40 g", 24, 6)]),
    dict(slug="karamilo-cocoa", name="Karamilo Cocoa", cat="biscuits",
         text="Biscuits filled with cocoa cream.",
         items=[("781", "", "68 g", 24, 6)]),
    dict(slug="pacho-cream-biscuits", name="Pacho cream biscuits", cat="biscuits",
         text="Cream biscuits in vanilla, strawberry, banana and cocoa.",
         items=[("310", "Vanilla", "72 g", 24, 6), ("311", "Strawberry", "72 g", 24, 6),
                ("312", "Banana", "72 g", 24, 6), ("313", "Cocoa", "72 g", 24, 6)]),
    dict(slug="prens-sandwich-biscuits", name="Prens sandwich biscuits", cat="biscuits",
         text="Sandwich biscuits with cocoa and hazelnut cream, from single packs to family packs.",
         items=[("370", "Mini Prens", "72 g", 24, 6), ("365", "Single pack", "25 g", 24, 12),
                ("360", "Family pack", "300 g", 12, 1), ("361", "", "120 g", 24, 1)]),
    dict(slug="pitaro-sandwich-biscuits", name="Pitaro sandwich biscuits", cat="biscuits",
         text="Sandwich biscuits in vanilla, strawberry, banana and cocoa-hazelnut.",
         items=[("350", "Vanilla", "160 g", 24, 1), ("350A", "Vanilla", "150 g", 24, 1),
                ("351", "Strawberry", "160 g", 24, 1), ("351A", "Strawberry", "150 g", 24, 1),
                ("352", "Banana", "160 g", 24, 1), ("352A", "Banana", "150 g", 24, 1),
                ("353", "Cocoa & hazelnut", "160 g", 24, 1), ("353A", "Cocoa & hazelnut", "150 g", 24, 1)]),
    dict(slug="maria-biscuits", name="Maria biscuits", cat="biscuits",
         text="Classic Maria biscuits, single roll or 3-roll multipack.",
         items=[("150", "Single", "115 g", 24, 1), ("150A", "3-pack", "3 × 115 g", 24, 1), ("150B", "3-pack", "3 × 115 g", 12, 1)]),
    dict(slug="susamli-sesame-biscuits", name="Susamlı sesame biscuits", cat="biscuits",
         text="Sesame biscuits in three pack colours, plus a 12-pack case.",
         items=[("251", "", "80 g", 24, 6), ("252", "", "80 g", 24, 6), ("253", "", "80 g", 24, 6), ("250", "", "80 g", 12, 12)]),
    dict(slug="peti-latte-2in1", name="Peti Latte 2in1", cat="biscuits",
         text="Caramel and milk flavoured Petit Beurre biscuits, 4-pack.",
         items=[("115", "", "400 g", 12, 1)]),
    dict(slug="peti-honey", name="Peti Honey", cat="biscuits",
         text="Milk and honey flavoured Petit Beurre biscuits, 4-pack.",
         items=[("116", "", "400 g", 12, 1)]),
    dict(slug="petit-beurre-biscuits", name="Petit Beurre biscuits", cat="biscuits",
         text="Petit Beurre tea biscuits, from 100 g rolls to 800 g family packs, plus a butter flavoured pack.",
         items=[("103", "", "100 g", 24, 1), ("111", "", "110 g", 24, 6), ("112", "", "110 g", 24, 6),
                ("113", "", "110 g", 24, 6), ("102", "", "200 g", 18, 1), ("104", "", "200 g", 18, 1),
                ("108", "", "330 g", 12, 1), ("109", "Butter flavoured", "330 g", 12, 1), ("101", "", "400 g", 10, 1),
                ("105", "", "600 g", 6, 1), ("100", "", "720 g", 6, 1), ("100A", "", "800 g", 6, 1)]),
    dict(slug="finger-biscuits", name="Finger biscuits", cat="biscuits",
         text="Finger tea biscuits in single packs and 6-pack family packs.",
         items=[("202", "", "90 g", 12, 12), ("201", "", "650 g", 6, 1), ("200", "6-pack", "900 g", 6, 1), ("200A", "6-pack", "840 g", 6, 1)]),
    dict(slug="piknik-biscuits", name="Piknik biscuits", cat="biscuits",
         text="Picnic biscuits in a roll pack.",
         items=[("170", "", "70 g", 24, 1)]),
]


# ---------- Coffee & instant beverages ("products (1).pdf", received 4 Nov 2026) ----------
# No item numbers in this PDF, so no "• Item" lines: the description is plain text.
COFFEE_PACKS = "Stick packs, tin cans, glass jars, PET jars, stand-up pouches"
PACKS_NOTE = "Pack formats and SKU sizes can be customised to your market."
BULK = "Also in bulk: 20 kg, 50 kg and 250 kg."
BLENDS = "Available blends: 10%, 15%, 33% and 100% coffee."
FRUIT_PACKS = "Stick packs, sachets, pouches, jars"


def _fruit(slug: str, fruit: str) -> dict:
    return dict(slug=f"instant-{slug}-drink-powder", name=f"Instant {fruit.lower()} drink powder", cat="instant-drinks",
                text=f"Instant {fruit.lower()} flavoured drink powder.\n\n{PACKS_NOTE}", packs=FRUIT_PACKS)


BEVERAGES = [
    dict(slug="agglomerated-instant-coffee", name="Agglomerated instant coffee", cat="coffee",
         text=f"Agglomerated instant coffee.\n\n{BLENDS}\nPacks: {COFFEE_PACKS}.\n{BULK}", packs=COFFEE_PACKS),
    dict(slug="spray-dried-instant-coffee", name="Spray-dried instant coffee", cat="coffee",
         text=f"Spray-dried instant coffee.\n\n{BLENDS}\nPacks: {COFFEE_PACKS}.\n{BULK}", packs=COFFEE_PACKS),
    dict(slug="freeze-dried-instant-coffee", name="Freeze-dried instant coffee", cat="coffee",
         text="Premium instant coffee with rich aroma and superior taste retention, preferred in high-end retail "
              f"markets.\n\nPacks: {COFFEE_PACKS}.\n{BULK}", packs=COFFEE_PACKS),
    dict(slug="coffee-3-in-1-premix", name="3-in-1 coffee premix", cat="coffee",
         text=f"Instant 3-in-1 coffee powder.\n\n{PACKS_NOTE}", packs=FRUIT_PACKS),
    dict(slug="hot-chocolate-powder", name="Hot chocolate powder", cat="health-drinks",
         text=f"Instant hot chocolate drink powder.\n\n{PACKS_NOTE}", packs=FRUIT_PACKS),
    *[_fruit(s, f) for s, f in [("lime", "Lime"), ("watermelon", "Watermelon"), ("pineapple", "Pineapple"),
                                ("mango", "Mango"), ("orange", "Orange"), ("passion-fruit", "Passion fruit"),
                                ("peach", "Peach"), ("guava", "Guava"), ("strawberry", "Strawberry")]],
]


def _description(p: dict) -> str:
    lines = [p["text"], "", "Items in our catalogue:"]
    for no, variant, weight, pcs, boxes in p["items"]:
        lines.append(f"• Item {no}{f' ({variant})' if variant else ''}: {weight}, {pcs} pieces per box, {boxes} per case")
    return "\n".join(lines)


def _pack_formats(p: dict) -> str:
    """Short summary for cards, e.g. "25 g, 40 g · 24 per box"."""
    weights = list(dict.fromkeys(w for _, _, w, _, _ in p["items"]))
    pcs = sorted({n for _, _, _, n, _ in p["items"]})
    text = f"{', '.join(weights)} · {'/'.join(map(str, pcs))} per box"
    return text[:255]


async def add_catalogue(db: AsyncSession) -> None:
    existing_cats = {c.slug: c for c in (await db.scalars(select(Category))).all()}
    for slug, name, desc, order in CATALOGUE_CATEGORIES:
        if slug not in existing_cats:
            existing_cats[slug] = Category(slug=slug, name=name, description=desc, sort_order=order, is_active=True)
            db.add(existing_cats[slug])
    await db.flush()  # gives the new categories their ids

    existing = set((await db.scalars(select(Product.slug))).all())
    added = 0
    for p in PRODUCTS:
        if p["slug"] in existing:
            continue
        db.add(Product(
            category_id=existing_cats[p["cat"]].id, slug=p["slug"], name=p["name"],
            description=_description(p), pack_formats=_pack_formats(p), moq="",
            image_path=f"/images/products/{p['slug']}.jpg", private_label=True, is_best_seller=False, is_active=True,
        ))
        added += 1
    for p in BEVERAGES:
        if p["slug"] in existing or p["cat"] not in existing_cats:  # coffee / health-drinks come from app.seed
            continue
        db.add(Product(
            category_id=existing_cats[p["cat"]].id, slug=p["slug"], name=p["name"],
            description=p["text"], pack_formats=p["packs"], moq="",
            image_path=f"/images/products/{p['slug']}.jpg", private_label=True, is_best_seller=False, is_active=True,
        ))
        added += 1
    await db.commit()
    total = len(PRODUCTS) + len(BEVERAGES)
    print(f"catalogue products: {added} added, {total - added} already there or skipped")


async def main() -> None:
    async with AsyncSessionLocal() as db:
        await add_catalogue(db)


if __name__ == "__main__":
    asyncio.run(main())
