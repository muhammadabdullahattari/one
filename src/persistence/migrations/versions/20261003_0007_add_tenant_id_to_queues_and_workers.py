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
    op.create_index(
        "ix_queues_tenant_name",
        "queues",
        ["tenant_id", "queue_name"],
        unique=False,
    )

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
