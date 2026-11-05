"""attendance enhancements: shifts, joined_on, and leave_requests

Revision ID: 0013
Revises: 0012
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0013'
down_revision: Union[str, None] = '0012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Shifts table
    op.create_table(
        'shifts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('is_night_shift', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_shifts_code'), 'shifts', ['code'], unique=True)

    # Seed default shifts
    op.execute("""
        INSERT INTO shifts (name, code, start_time, end_time, is_night_shift, is_active, created_at, updated_at)
        VALUES 
            ('General Shift', 'GEN', '09:30:00', '18:30:00', false, true, now(), now()),
            ('Morning Shift', 'MORN', '06:00:00', '14:30:00', false, true, now(), now()),
            ('Evening Shift', 'EVE', '14:00:00', '22:30:00', false, true, now(), now()),
            ('Night Shift', 'NIGHT', '22:00:00', '06:30:00', true, true, now(), now())
        ON CONFLICT (code) DO NOTHING;
    """)

    # 2. Add joined_on to users and link shift_id
    op.add_column('users', sa.Column('joined_on', sa.Date(), nullable=True))
    op.execute("""
        UPDATE users 
        SET joined_on = COALESCE(approved_at::date, created_at::date, CURRENT_DATE) 
        WHERE joined_on IS NULL;
    """)

    # Link users.shift_id as a foreign key to shifts.id
    op.create_foreign_key('fk_users_shift_id', 'users', 'shifts', ['shift_id'], ['id'], ondelete='SET NULL')

    # Default existing users to the General Shift
    op.execute("""
        UPDATE users 
        SET shift_id = (SELECT id FROM shifts WHERE code = 'GEN' LIMIT 1) 
        WHERE shift_id IS NULL;
    """)

    # 3. Leave requests table
    op.create_table(
        'leave_requests',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('leave_type', sa.String(length=30), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('is_half_day', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('half_day_session', sa.String(length=20), nullable=True),
        sa.Column('reason', sa.String(length=500), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
        sa.Column('decided_by', sa.Integer(), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejection_reason', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['decided_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_leave_requests_user_id'), 'leave_requests', ['user_id'], unique=False)
    op.create_index(op.f('ix_leave_requests_start_date'), 'leave_requests', ['start_date'], unique=False)
    op.create_index(op.f('ix_leave_requests_end_date'), 'leave_requests', ['end_date'], unique=False)
    op.create_index(op.f('ix_leave_requests_status'), 'leave_requests', ['status'], unique=False)


def downgrade() -> None:
    op.drop_table('leave_requests')
    op.drop_constraint('fk_users_shift_id', 'users', type_='foreignkey')
    op.drop_column('users', 'joined_on')
    op.drop_table('shifts')

