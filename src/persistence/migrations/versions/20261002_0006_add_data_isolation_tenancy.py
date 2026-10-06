"""add data isolation tenancy columns and composite indexes

Revision ID: 20261002_0006
Revises: 20261001_0005
Create Date: 2026-10-02

"""

from alembic import op
import sqlalchemy as sa

revision = "20261002_0006"
down_revision = "20261001_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("tenant_id", sa.String(length=64), nullable=False, server_default="default"),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"], unique=False)

    op.add_column(
        "schedules",
        sa.Column("tenant_id", sa.String(length=64), nullable=False, server_default="default"),
    )
    op.create_index("ix_schedules_tenant_id", "schedules", ["tenant_id"], unique=False)
    op.create_index(
        "ix_schedules_tenant_due",
        "schedules",
        ["tenant_id", "enabled", "next_run_at"],
        unique=False,
    )

    op.add_column(
        "dlq_entries",
        sa.Column("tenant_id", sa.String(length=64), nullable=False, server_default="default"),
    )
    op.execute(
        "UPDATE dlq_entries SET tenant_id = tasks.tenant_id FROM tasks WHERE dlq_entries.task_id = tasks.task_id"
    )
    op.create_index("ix_dlq_entries_tenant_id", "dlq_entries", ["tenant_id"], unique=False)
    op.create_index(
        "ix_dlq_tenant_dead",
        "dlq_entries",
        ["tenant_id", "dead_at"],
        unique=False,
    )

    op.create_index(
        "ix_tasks_tenant_queue_status_created",
        "tasks",
        ["tenant_id", "queue", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_tasks_tenant_status_created",
        "tasks",
        ["tenant_id", "status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tasks_tenant_status_created", table_name="tasks")
    op.drop_index("ix_tasks_tenant_queue_status_created", table_name="tasks")
    op.drop_index("ix_dlq_tenant_dead", table_name="dlq_entries")
    op.drop_index("ix_dlq_entries_tenant_id", table_name="dlq_entries")
    op.drop_column("dlq_entries", "tenant_id")
    op.drop_index("ix_schedules_tenant_due", table_name="schedules")
    op.drop_index("ix_schedules_tenant_id", table_name="schedules")
    op.drop_column("schedules", "tenant_id")
    op.drop_index("ix_users_tenant_id", table_name="users")
    op.drop_column("users", "tenant_id")
