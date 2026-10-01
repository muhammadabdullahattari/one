"""add schedule_id index to tasks

Revision ID: 20261001_0005
Revises: 20260930_0004
Create Date: 2026-10-01

"""

from alembic import op

revision = "20261001_0005"
down_revision = "20260930_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_tasks_schedule_id", "tasks", ["schedule_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tasks_schedule_id", table_name="tasks")
