"""work pages: indexes for "everything one person did in a time range" (Team work, My work timeline)

The timeline reads one person's lead notes (calls, emails, notes, outcomes), finished tasks and chat
messages between two times. Without these, each lookup would read the whole table. Only adds
indexes: no data changes.

Revision ID: 0027
Revises: 0026
"""
from typing import Sequence, Union

from alembic import op

revision: str = '0027'
down_revision: Union[str, None] = '0026'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_lead_notes_user_created', 'lead_notes', ['user_id', 'created_at'])
    op.create_index('ix_tasks_assignee_completed', 'tasks', ['assignee_id', 'completed_at'])
    op.create_index('ix_chat_messages_sender_created', 'chat_messages', ['sender_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_chat_messages_sender_created', table_name='chat_messages')
    op.drop_index('ix_tasks_assignee_completed', table_name='tasks')
    op.drop_index('ix_lead_notes_user_created', table_name='lead_notes')
