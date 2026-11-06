"""multi-punch attendance: punches table and total_seconds tracking

Revision ID: 0014
Revises: 0013
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0014'
down_revision: Union[str, None] = '0013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add total_seconds to attendance
    op.add_column('attendance', sa.Column('total_seconds', sa.Integer(), server_default='0', nullable=False))

    # Backfill total_seconds for existing check-ins with check-outs
    op.execute("""
        UPDATE attendance
        SET total_seconds = GREATEST(0, ROUND(EXTRACT(EPOCH FROM (check_out_at - check_in_at))))::integer
        WHERE check_in_at IS NOT NULL AND check_out_at IS NOT NULL
    """)

    # 2. Create attendance_punches table
    op.create_table(
        'attendance_punches',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('attendance_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('punch_type', sa.String(length=10), nullable=False),
        sa.Column('punched_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('notes', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['attendance_id'], ['attendance.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_attendance_punches_attendance_id'), 'attendance_punches', ['attendance_id'], unique=False)
    op.create_index(op.f('ix_attendance_punches_user_id'), 'attendance_punches', ['user_id'], unique=False)
    op.create_index(op.f('ix_attendance_punches_day'), 'attendance_punches', ['day'], unique=False)

    # Backfill existing punches from attendance table using individual statements
    op.execute("""
        INSERT INTO attendance_punches (attendance_id, user_id, day, punch_type, punched_at, created_at, updated_at)
        SELECT id, user_id, day, 'in', check_in_at, created_at, updated_at
        FROM attendance
        WHERE check_in_at IS NOT NULL
    """)

    op.execute("""
        INSERT INTO attendance_punches (attendance_id, user_id, day, punch_type, punched_at, created_at, updated_at)
        SELECT id, user_id, day, 'out', check_out_at, created_at, updated_at
        FROM attendance
        WHERE check_out_at IS NOT NULL
    """)


def downgrade() -> None:
    op.drop_index(op.f('ix_attendance_punches_day'), table_name='attendance_punches')
    op.drop_index(op.f('ix_attendance_punches_user_id'), table_name='attendance_punches')
    op.drop_index(op.f('ix_attendance_punches_attendance_id'), table_name='attendance_punches')
    op.drop_table('attendance_punches')
    op.drop_column('attendance', 'total_seconds')
