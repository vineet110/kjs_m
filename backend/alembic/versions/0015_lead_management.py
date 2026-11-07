"""lead management: who typed in an internal lead, and the admin-set staff fields (employee code,
branch, reporting to) from the User Creation Form

Revision ID: 0015
Revises: 0014
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0015'
down_revision: Union[str, None] = '0014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing staff get empty values; the admin fills them in from the Users page.
    op.add_column('users', sa.Column('employee_code', sa.String(40), nullable=False, server_default=''))
    op.add_column('users', sa.Column('branch', sa.String(80), nullable=False, server_default=''))
    op.add_column('users', sa.Column('reporting_to', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    # Website and Koko leads have no "created by" (a visitor sent them): empty.
    op.add_column('leads', sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))


def downgrade() -> None:
    op.drop_column('leads', 'created_by')
    op.drop_column('users', 'reporting_to')
    op.drop_column('users', 'branch')
    op.drop_column('users', 'employee_code')
