"""product offer: an optional "Up to X% OFF" percentage per product (UI step 6)

Revision ID: 0012
Revises: 0011
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0012'
down_revision: Union[str, None] = '0011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Empty for every existing product: no badge until staff set an offer. The database also refuses
    # values outside 1 to 90, whatever writes them.
    op.add_column('products', sa.Column('offer_percent', sa.Integer(), nullable=True))
    op.create_check_constraint('ck_products_offer_percent', 'products',
                               'offer_percent IS NULL OR offer_percent BETWEEN 1 AND 90')


def downgrade() -> None:
    op.drop_constraint('ck_products_offer_percent', 'products', type_='check')
    op.drop_column('products', 'offer_percent')
