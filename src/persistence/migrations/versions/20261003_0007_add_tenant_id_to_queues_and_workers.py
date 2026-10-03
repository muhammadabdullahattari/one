"""add tenant_id to queues and workers for full tenant isolation

Revision ID: 20261003_0007
Revises: 20261002_0006
Create Date: 2026-10-03

"""

from alembic import op
import sqlalchemy as sa

revision = "20261003_0007"
down_revision = "20261002_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add tenant_id to queues table
    #    Queues are system-global resources that must be scoped per tenant.
    #    Existing rows default to "default" so the seed "default" queue keeps working.
    op.add_column(
        "queues",
        sa.Column(
            "tenant_id",
            sa.String(length=64),
            nullable=False,
            server_default="default",
        ),
    )
    op.create_index("ix_queues_tenant_id", "queues", ["tenant_id"], unique=False)
    # Composite index used by list_queues(tenant_id=...) queries
    op.create_index(
        "ix_queues_tenant_name",
        "queues",
        ["tenant_id", "queue_name"],
        unique=False,
    )

    # 2. Add tenant_id to workers table
    #    Workers register under a specific tenant so list_workers can be scoped.
    #    Existing rows default to "default".
    op.add_column(
        "workers",
        sa.Column(
            "tenant_id",
            sa.String(length=64),
            nullable=False,
            server_default="default",
        ),
    )
    op.create_index("ix_workers_tenant_id", "workers", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_workers_tenant_id", table_name="workers")
    op.drop_column("workers", "tenant_id")

    op.drop_index("ix_queues_tenant_name", table_name="queues")
    op.drop_index("ix_queues_tenant_id", table_name="queues")
    op.drop_column("queues", "tenant_id")
