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


def split_description(text: str) -> tuple[str, list[dict]]:
    """(the description without its item lines, the items)."""
    keep, items = [], []
    for line in (text or "").split("\n"):
        m = ITEM.match(line.strip())
        if m:
            items.append({"no": m[1], "variant": m[2] or "", "weight": m[3], "pieces": int(m[4]),
                          "per_case": int(m[5])})
        elif line.strip() != HEADER:
            keep.append(line)
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
