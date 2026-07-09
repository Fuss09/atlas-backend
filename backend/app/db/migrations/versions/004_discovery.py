"""Module 04 — Create discovery_jobs and discovery_sources tables

Revision ID: 004_discovery
Revises: 003_themes
Create Date: 2025-01-04 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004_discovery"
down_revision: str | None = "003_themes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── discovery_jobs ─────────────────────────────────────────────────────────
    op.create_table(
        "discovery_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("triggered_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("companies_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("companies_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("companies_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("companies_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_discovery_jobs_source", "discovery_jobs", ["source"])
    op.create_index("ix_discovery_jobs_status", "discovery_jobs", ["status"])
    op.create_index("ix_discovery_jobs_created_at", "discovery_jobs", ["created_at"])

    # ── discovery_sources ──────────────────────────────────────────────────────
    op.create_table(
        "discovery_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("discovery_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("external_url", sa.String(512), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("action", sa.String(20), nullable=False, server_default="created"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_discovery_sources_company_id", "discovery_sources", ["company_id"])
    op.create_index("ix_discovery_sources_job_id", "discovery_sources", ["job_id"])
    op.create_index("ix_discovery_sources_source", "discovery_sources", ["source"])


def downgrade() -> None:
    op.drop_index("ix_discovery_sources_source", table_name="discovery_sources")
    op.drop_index("ix_discovery_sources_job_id", table_name="discovery_sources")
    op.drop_index("ix_discovery_sources_company_id", table_name="discovery_sources")
    op.drop_table("discovery_sources")
    op.drop_index("ix_discovery_jobs_created_at", table_name="discovery_jobs")
    op.drop_index("ix_discovery_jobs_status", table_name="discovery_jobs")
    op.drop_index("ix_discovery_jobs_source", table_name="discovery_jobs")
    op.drop_table("discovery_jobs")
