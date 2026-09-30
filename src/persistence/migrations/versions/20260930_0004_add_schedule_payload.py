"""add payload column to schedules

Revision ID: 20260930_0004
Revises: 20260930_0003
Create Date: 2026-09-30

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260930_0004"
down_revision = "20260930_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("schedules", sa.Column("payload", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("schedules", "payload")
