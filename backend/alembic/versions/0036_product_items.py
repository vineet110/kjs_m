"""Products: catalogue items in their own column (R19)

The items were lines inside the description ("• Item 801 (variant): 25 g, 24 pieces per box, 6 per case",
under "Items in our catalogue:"). They move to products.items (JSON list) and leave the description, so an
item can no longer vanish because its line was written a little differently. Downgrade writes them back.

Revision ID: 0036
Revises: 0035
"""
import json
import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = '0036'
down_revision: Union[str, None] = '0035'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The same pattern the website used (frontend lib/catalogue.ts), copied here: a migration must not depend on
# app code that can change later
ITEM = re.compile(r"^• Item (\S+)(?: \((.+)\))?: (.+?), (\d+) pieces per box, (\d+) per case$")
HEADER = "Items in our catalogue:"


def _fits(i: dict, taken: set[str]) -> bool:
    """The same limits the API checks (schemas/catalog.py ProductItem), copied for the same reason as ITEM.
    A line outside them stays in the description: a stored item the API refuses would break every product list."""
    return (len(i["no"]) <= 20 and len(i["variant"]) <= 60 and 1 <= len(i["weight"]) <= 30
            and 1 <= i["pieces"] <= 100000 and 1 <= i["per_case"] <= 100000 and i["no"] not in taken)


def split_description(text: str) -> tuple[str, list[dict]]:
    """(the description without the item lines that moved, the items). Lines that don't fit stay, under the
    'Items in our catalogue:' header if they had one, so nothing disappears and staff can move them by hand."""
    keep, items, taken = [], [], set()
    for line in (text or "").split("\n"):
        m = ITEM.match(line.strip())
        item = m and {"no": m[1], "variant": m[2] or "", "weight": m[3], "pieces": int(m[4]), "per_case": int(m[5])}
        if item and _fits(item, taken):
            items.append(item)
            taken.add(item["no"])
        else:
            keep.append(line)
    left = [line for line in keep if line.strip().startswith("• Item")]
    if not left:  # every item moved: the header has nothing under it any more
        keep = [line for line in keep if line.strip() != HEADER]
    return "\n".join(keep).rstrip(), items


def item_line(i: dict) -> str:
    variant = f" ({i['variant']})" if i.get("variant") else ""
    return f"• Item {i['no']}{variant}: {i['weight']}, {i['pieces']} pieces per box, {i['per_case']} per case"


def upgrade() -> None:
    op.add_column('products', sa.Column('items', JSONB(), nullable=False, server_default='[]'))
    conn = op.get_bind()
    for pid, text in conn.execute(sa.text("SELECT id, description FROM products")).all():
        description, items = split_description(text)
        if items:
            conn.execute(sa.text("UPDATE products SET description = :d, items = CAST(:i AS jsonb) WHERE id = :id"),
                         {"d": description, "i": json.dumps(items), "id": pid})


def downgrade() -> None:
    conn = op.get_bind()
    for pid, text, items in conn.execute(sa.text("SELECT id, description, items FROM products")).all():
        if items:
            lines = [text, "", HEADER, *[item_line(i) for i in items]] if text else [HEADER, *[item_line(i) for i in items]]
            conn.execute(sa.text("UPDATE products SET description = :d WHERE id = :id"),
                         {"d": "\n".join(lines), "id": pid})
    op.drop_column('products', 'items')
