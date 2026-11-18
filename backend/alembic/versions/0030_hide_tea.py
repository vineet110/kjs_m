"""Hide the Tea category (data only)

Tea has no products yet. Until now it was hidden by a list in the frontend (HIDDEN_CATEGORIES), while the
database said it was on, so Koko and the API still showed it. Categories are now shown and hidden in
Admin > Products > Categories, so the database says Tea is off and the frontend list is gone.

Changes one row; no table changes. Runs on a database without Tea too (it changes nothing then).

Number 0030: 0027-0029 are taken by the open monitoring PRs (#83-#85). Whichever merges second points its
down_revision at the other.

Revision ID: 0030
Revises: 0026
"""
from typing import Sequence, Union

from alembic import op

revision: str = '0030'
down_revision: Union[str, None] = '0026'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE categories SET is_active = false WHERE slug = 'tea'")


def downgrade() -> None:
    op.execute("UPDATE categories SET is_active = true WHERE slug = 'tea'")
