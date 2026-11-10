"""KJS Chat: channels, group chats and DMs (phase 1)

chat_channels: one row per channel, group chat or DM (kind tells them apart). dm_key is unique: for a DM
it is the two user ids, smaller first ("12:45"), so the database itself stops a second DM for the same
pair. Empty (NULL) for channels and groups.
chat_members: who is in which channel. last_read_message_id drives the unread counts.
chat_messages: the messages; mentions = the user ids @mentioned in it. The (channel_id, id) index makes
"the 50 before message X" fast.

Number 0020: 0019 is the Lead Harvester (#53), merged first on 10 Nov, so this one comes after it.

Only creates new tables: no existing data is touched.

Revision ID: 0020
Revises: 0019
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = '0020'
down_revision: Union[str, None] = '0019'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'chat_channels',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('kind', sa.String(10), nullable=False),  # channel | group | dm
        sa.Column('name', sa.String(80), server_default='', nullable=False),
        sa.Column('description', sa.String(500), server_default='', nullable=False),
        sa.Column('is_private', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('dm_key', sa.String(30), nullable=True, unique=True),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind IN ('channel', 'group', 'dm')", name='ck_chat_channels_kind'),
    )
    op.create_table(
        'chat_members',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('channel_id', sa.Integer(), sa.ForeignKey('chat_channels.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('role', sa.String(10), server_default='member', nullable=False),  # owner | member
        sa.Column('last_read_message_id', sa.Integer(), server_default='0', nullable=False),
        sa.Column('muted', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('channel_id', 'user_id', name='uq_chat_members_channel_user'),
    )
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('channel_id', sa.Integer(), sa.ForeignKey('chat_channels.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sender_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('mentions', JSONB(), server_default='[]', nullable=False),  # user ids @mentioned
        sa.Column('parent_id', sa.Integer(), sa.ForeignKey('chat_messages.id'), nullable=True),  # replies (phase 2)
        sa.Column('edited_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_chat_messages_channel_id_id', 'chat_messages', ['channel_id', 'id'])


def downgrade() -> None:
    op.drop_index('ix_chat_messages_channel_id_id', table_name='chat_messages')
    op.drop_table('chat_messages')
    op.drop_table('chat_members')
    op.drop_table('chat_channels')
