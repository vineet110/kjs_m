"""website content: offers, site texts, partner applications, koko chats

Revision ID: 0009
Revises: 0008
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0009'
down_revision: Union[str, None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _stamps():
    return [
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    ]


def upgrade() -> None:
    op.create_table(
        'offers',
        sa.Column('text', sa.String(200), nullable=False),
        sa.Column('link', sa.String(255), nullable=False),
        sa.Column('starts_at', sa.DateTime(timezone=True)),
        sa.Column('ends_at', sa.DateTime(timezone=True)),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        *_stamps(),
    )
    op.create_table(
        'site_texts',
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('updated_by', sa.Integer(), sa.ForeignKey('users.id')),
        *_stamps(),
    )
    op.create_index('ix_site_texts_key', 'site_texts', ['key'], unique=True)
    op.create_table(
        'partner_applications',
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('company', sa.String(200), nullable=False),
        sa.Column('partner_type', sa.String(40), nullable=False),
        sa.Column('country', sa.String(80), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('phone', sa.String(30), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('ip_hash', sa.String(64)),
        sa.Column('consent_at', sa.DateTime(timezone=True), nullable=False),
        *_stamps(),
    )
    op.create_table(
        'koko_chats',
        sa.Column('chat_id', sa.String(40), nullable=False),
        sa.Column('page', sa.String(255), nullable=False),
        sa.Column('messages', postgresql.JSONB(), nullable=False),
        sa.Column('suggested_enquiry', sa.Boolean(), nullable=False),
        sa.Column('ip_hash', sa.String(64)),
        *_stamps(),
    )
    op.create_index('ix_koko_chats_chat_id', 'koko_chats', ['chat_id'], unique=True)


def downgrade() -> None:
    op.drop_table('koko_chats')
    op.drop_table('partner_applications')
    op.drop_table('site_texts')
    op.drop_table('offers')
