"""Module 09 — Create price_snapshots and score_snapshots tables

Revision ID: 009_snapshots
Revises: 008_watchlist
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "009_snapshots"
down_revision: str | None = "008_watchlist"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "price_snapshots",
        # AtlasBase
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        # Snapshot
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("price", sa.Numeric(18, 6), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.Column("market_cap", sa.BigInteger(), nullable=True),
        sa.Column("source", sa.String(30), nullable=False, server_default="yfinance"),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_price_snapshots_company_id", "price_snapshots", ["company_id"])
    op.create_index("ix_price_snapshots_captured_at", "price_snapshots", ["captured_at"])
    op.create_index("ix_price_snapshots_is_deleted", "price_snapshots", ["is_deleted"])
    op.create_index(
        "ix_price_snapshots_company_time", "price_snapshots", ["company_id", "captured_at"]
    )

    op.create_table(
        "score_snapshots",
        # AtlasBase
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        # Snapshot
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("conviction", sa.String(20), nullable=False),
        sa.Column("stage", sa.String(20), nullable=False),
        sa.Column("scoring_version", sa.Integer(), nullable=False),
        sa.Column("components", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_score_snapshots_company_id", "score_snapshots", ["company_id"])
    op.create_index("ix_score_snapshots_captured_at", "score_snapshots", ["captured_at"])
    op.create_index("ix_score_snapshots_is_deleted", "score_snapshots", ["is_deleted"])
    op.create_index(
        "ix_score_snapshots_company_time", "score_snapshots", ["company_id", "captured_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_score_snapshots_company_time", table_name="score_snapshots")
    op.drop_index("ix_score_snapshots_is_deleted", table_name="score_snapshots")
    op.drop_index("ix_score_snapshots_captured_at", table_name="score_snapshots")
    op.drop_index("ix_score_snapshots_company_id", table_name="score_snapshots")
    op.drop_table("score_snapshots")

    op.drop_index("ix_price_snapshots_company_time", table_name="price_snapshots")
    op.drop_index("ix_price_snapshots_is_deleted", table_name="price_snapshots")
    op.drop_index("ix_price_snapshots_captured_at", table_name="price_snapshots")
    op.drop_index("ix_price_snapshots_company_id", table_name="price_snapshots")
    op.drop_table("price_snapshots")
