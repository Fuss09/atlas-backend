"""Module 10 — Create catalysts table

Revision ID: 010_catalysts
Revises: 009_snapshots
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "010_catalysts"
down_revision: str | None = "009_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "catalysts",
        # AtlasBase
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        # Catalyst
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("catalyst_type", sa.String(30), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("expected_date", sa.Date(), nullable=False),
        sa.Column("date_precision", sa.String(10), nullable=False, server_default="day"),
        sa.Column("status", sa.String(20), nullable=False, server_default="upcoming"),
        sa.Column("source", sa.String(30), nullable=False, server_default="manual"),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("external_id", sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id", name="uq_catalysts_external_id"),
    )
    op.create_index("ix_catalysts_company_id", "catalysts", ["company_id"])
    op.create_index("ix_catalysts_expected_date", "catalysts", ["expected_date"])
    op.create_index("ix_catalysts_is_deleted", "catalysts", ["is_deleted"])


def downgrade() -> None:
    op.drop_index("ix_catalysts_is_deleted", table_name="catalysts")
    op.drop_index("ix_catalysts_expected_date", table_name="catalysts")
    op.drop_index("ix_catalysts_company_id", table_name="catalysts")
    op.drop_table("catalysts")
