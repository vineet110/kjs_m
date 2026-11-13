"""Staff: job titles and rejected sign-ups

users.job_title: a label such as "Sales Executive", picked from job_titles. It gives no access: what a
person may do comes only from their permissions (and role admin / employee, set by "Admin access").
users.rejection_reason: why a sign-up was rejected (status "rejected"; approved_by / approved_at then
record who rejected it and when).
job_titles: the list admins pick from and add to. Names are unique whatever their case.

Only adds a table and two columns with defaults: existing rows and the old code keep working.

Revision ID: 0021
Revises: 0020
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0021'
down_revision: Union[str, None] = '0020'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('job_title', sa.String(60), server_default='', nullable=False))
    op.add_column('users', sa.Column('rejection_reason', sa.String(500), nullable=True))
    op.create_table(
        'job_titles',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(60), nullable=False),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # "Sales executive" and "sales Executive" are the same title
    op.create_index('uq_job_titles_name_lower', 'job_titles', [sa.text('lower(name)')], unique=True)


def downgrade() -> None:
    op.drop_index('uq_job_titles_name_lower', table_name='job_titles')
    op.drop_table('job_titles')
    op.drop_column('users', 'rejection_reason')
    op.drop_column('users', 'job_title')
