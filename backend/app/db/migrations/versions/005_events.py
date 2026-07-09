"""Module 05 — Create events table

Revision ID: 005_events
Revises: 004_discovery
Create Date: 2025-01-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005_events"
down_revision: str | None = "004_discovery"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "events",
        # AtlasBase
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        # FK
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Classification
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("importance", sa.String(20), nullable=False, server_default="medium"),
        # Contenu
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        # Temporalité
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        # Source
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_url", sa.String(512), nullable=True),
        sa.Column("source_id", sa.String(255), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        # Scoring
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        # Traitement
        sa.Column("is_processed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("processing_version", sa.Integer(), nullable=True),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"], ondelete="CASCADE"
        ),
    )

    # Index standards
    op.create_index("ix_events_is_deleted", "events", ["is_deleted"])
    op.create_index("ix_events_company_id", "events", ["company_id"])
    op.create_index("ix_events_event_type", "events", ["event_type"])
    op.create_index("ix_events_importance", "events", ["importance"])
    op.create_index("ix_events_source", "events", ["source"])
    op.create_index("ix_events_occurred_at", "events", ["occurred_at"])
    op.create_index("ix_events_is_processed", "events", ["is_processed"])
    op.create_index("ix_events_source_id", "events", ["source_id"])

    # Index composites pour les requêtes Opportunity Engine
    op.create_index(
        "ix_events_company_occurred",
        "events",
        ["company_id", "occurred_at"],
    )
    op.create_index(
        "ix_events_unprocessed",
        "events",
        ["is_processed", "occurred_at"],
        postgresql_where=sa.text("is_processed = false AND is_deleted = false"),
    )
    # Déduplication par source + source_id
    op.create_index(
        "ix_events_source_source_id",
        "events",
        ["source", "source_id"],
        postgresql_where=sa.text("source_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_events_source_source_id", table_name="events")
    op.drop_index("ix_events_unprocessed", table_name="events")
    op.drop_index("ix_events_company_occurred", table_name="events")
    op.drop_index("ix_events_source_id", table_name="events")
    op.drop_index("ix_events_is_processed", table_name="events")
    op.drop_index("ix_events_occurred_at", table_name="events")
    op.drop_index("ix_events_source", table_name="events")
    op.drop_index("ix_events_importance", table_name="events")
    op.drop_index("ix_events_event_type", table_name="events")
    op.drop_index("ix_events_company_id", table_name="events")
    op.drop_index("ix_events_is_deleted", table_name="events")
    op.drop_table("events")
