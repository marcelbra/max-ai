"""initial

Revision ID: ba061ec650de
Revises:
Create Date: 2026-02-01 00:42:48.073250

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ba061ec650de'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PMS Category
    op.create_table(
        'pms_category',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('emoji', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
    )

    # PMS Statement
    op.create_table(
        'pms_statement',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('category_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pms_category.id', ondelete='CASCADE'), nullable=False),
        sa.Column('statement', sa.Text(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
    )

    # Role
    op.create_table(
        'role',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('pms_category_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pms_category.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('pms_anchor', sa.Text(), nullable=True),
        sa.Column('current_state', sa.Text(), nullable=True),
        sa.Column('context', sa.Text(), nullable=True),
        sa.Column('target_budget', sa.Integer(), nullable=True),
    )

    # Recurring Goal
    op.create_table(
        'recurring_goal',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('role.id', ondelete='CASCADE'), nullable=False),
        sa.Column('activity', sa.String(), nullable=False),
        sa.Column('target_amount', sa.Float(), nullable=False),
        sa.Column('target_time', sa.Integer(), nullable=False),
        sa.Column('context', sa.Text(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
    )

    # Unique Goal
    op.create_table(
        'unique_goal',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('role.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('deadline', sa.Date(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='not_started'),
        sa.Column('context', sa.Text(), nullable=True),
        sa.Column('depends_on', postgresql.UUID(as_uuid=True), sa.ForeignKey('unique_goal.id', ondelete='SET NULL'), nullable=True),
    )

    # Task Instance
    op.create_table(
        'task_instance',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('role.id', ondelete='SET NULL'), nullable=True),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('scheduled_date', sa.Date(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('target_time', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('context', sa.Text(), nullable=True),
        sa.Column('calendar_event_id', sa.String(), nullable=True),
    )

    # Create indexes for common queries
    op.create_index('ix_task_instance_scheduled_date', 'task_instance', ['scheduled_date'])
    op.create_index('ix_task_instance_status', 'task_instance', ['status'])


def downgrade() -> None:
    op.drop_index('ix_task_instance_status')
    op.drop_index('ix_task_instance_scheduled_date')
    op.drop_table('task_instance')
    op.drop_table('unique_goal')
    op.drop_table('recurring_goal')
    op.drop_table('role')
    op.drop_table('pms_statement')
    op.drop_table('pms_category')
