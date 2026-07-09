"""Module 06 — Create opportunity_scores table

Revision ID: 006_opportunity_scores
Revises: 005_events
Create Date: 2026-07-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006_opportunity_scores"
down_revision: str | None = "005_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "opportunity_scores",
        # AtlasBase
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        # FK — une seule ligne active par entreprise
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Score global
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("conviction", sa.String(20), nullable=False),
        sa.Column("stage", sa.String(20), nullable=False),
        sa.Column("stage_rationale", sa.String(500), nullable=False),
        # Détail explicable
        sa.Column("components", postgresql.JSONB(), nullable=False),
        sa.Column("positive_factors", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("negative_factors", postgresql.JSONB(), nullable=False, server_default="[]"),
        # Traçabilité
        sa.Column("scoring_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("company_id", name="uq_opportunity_scores_company_id"),
    )

    op.create_index("ix_opportunity_scores_is_deleted", "opportunity_scores", ["is_deleted"])
    op.create_index("ix_opportunity_scores_company_id", "opportunity_scores", ["company_id"], unique=True)
    op.create_index("ix_opportunity_scores_score", "opportunity_scores", ["score"])
    op.create_index("ix_opportunity_scores_conviction", "opportunity_scores", ["conviction"])
    op.create_index("ix_opportunity_scores_stage", "opportunity_scores", ["stage"])

    # Index composite pour GET /opportunities (tri par score, exclusion soft-deleted)
    op.create_index(
        "ix_opportunity_scores_ranking",
        "opportunity_scores",
        ["is_deleted", "score"],
    )


def downgrade() -> None:
    op.drop_index("ix_opportunity_scores_ranking", table_name="opportunity_scores")
    op.drop_index("ix_opportunity_scores_stage", table_name="opportunity_scores")
    op.drop_index("ix_opportunity_scores_conviction", table_name="opportunity_scores")
    op.drop_index("ix_opportunity_scores_score", table_name="opportunity_scores")
    op.drop_index("ix_opportunity_scores_company_id", table_name="opportunity_scores")
    op.drop_index("ix_opportunity_scores_is_deleted", table_name="opportunity_scores")
    op.drop_table("opportunity_scores")
