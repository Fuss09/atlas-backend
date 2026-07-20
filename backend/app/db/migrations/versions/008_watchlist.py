"""Module 08 — Create watchlist_items table

Revision ID: 008_watchlist
Revises: 007_graph_relations
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008_watchlist"
down_revision: str | None = "007_graph_relations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "watchlist_items",
        # AtlasBase
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        # Watchlist
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("notes", sa.String(500), nullable=True),
        # Contraintes
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", name="uq_watchlist_company"),
    )

    op.create_index("ix_watchlist_items_company_id", "watchlist_items", ["company_id"])
    op.create_index("ix_watchlist_items_is_deleted", "watchlist_items", ["is_deleted"])


def downgrade() -> None:
    op.drop_index("ix_watchlist_items_is_deleted", table_name="watchlist_items")
    op.drop_index("ix_watchlist_items_company_id", table_name="watchlist_items")
    op.drop_table("watchlist_items")
