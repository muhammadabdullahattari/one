from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from src.security.password import hash_password

revision: str = "20260930_0002"
down_revision: str | None = "20260925_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="operator"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_users"),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "projects",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("project_id", name="pk_projects"),
        sa.UniqueConstraint("slug", name="uq_projects_slug"),
    )
    op.create_index("ix_projects_slug", "projects", ["slug"])

    op.add_column(
        "api_credentials",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "api_credentials",
        sa.Column("key_prefix", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "api_credentials",
        sa.Column(
            "scopes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[\"*\"]'::jsonb"),
        ),
    )
    op.create_foreign_key(
        "fk_api_credentials_project_id",
        "api_credentials",
        "projects",
        ["project_id"],
        ["project_id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_api_credentials_project_id", "api_credentials", ["project_id"])

    admin_hash = hash_password("adminpassword123")
    op.execute(
        sa.text(
            f"""
            INSERT INTO users (user_id, username, email, password_hash, role)
            VALUES
                (gen_random_uuid(), 'admin', 'admin@taskengine.internal', '{admin_hash}', 'admin')
            ON CONFLICT (username) DO NOTHING;
            """
        )
    )


def downgrade() -> None:
    op.drop_constraint("fk_api_credentials_project_id", "api_credentials", type_="foreignkey")
    op.drop_index("ix_api_credentials_project_id", table_name="api_credentials")
    op.drop_column("api_credentials", "scopes")
    op.drop_column("api_credentials", "key_prefix")
    op.drop_column("api_credentials", "project_id")
    op.drop_index("ix_projects_slug", table_name="projects")
    op.drop_table("projects")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
