"""Initial migration - create users table

Revision ID: 001_initial
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create enums
    op.execute("CREATE TYPE auth_provider_enum AS ENUM ('local', 'google', 'github')")
    op.execute("CREATE TYPE user_role_enum AS ENUM ('user', 'analyst', 'admin')")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("avatar_url", sa.String(512), nullable=True),
        sa.Column("hashed_password", sa.Text(), nullable=True),
        sa.Column(
            "auth_provider",
            postgresql.ENUM("user", "analyst", "admin", name="user_role_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("oauth_provider_id", sa.String(255), nullable=True),
        sa.Column(
            "role",
            postgresql.ENUM("user", "analyst", "admin", name="user_role_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("preferred_language", sa.String(10), nullable=False, server_default="fr"),
        # TimestampMixin
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # SoftDeleteMixin
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Indexes
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_is_deleted", "users", ["is_deleted"])


def downgrade() -> None:
    op.drop_index("ix_users_is_deleted", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS auth_provider_enum")
    op.execute("DROP TYPE IF EXISTS user_role_enum")
