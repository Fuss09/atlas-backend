"""Module 07 — Create graph_relations table

Revision ID: 007_graph_relations
Revises: 006_opportunity_scores
Create Date: 2025-01-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007_graph_relations"
down_revision: str | None = "006_opportunity_scores"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "graph_relations",
        # AtlasBase
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        # Nœud source
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_label", sa.String(255), nullable=True),
        # Nœud cible
        sa.Column("target_type", sa.String(30), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_label", sa.String(255), nullable=True),
        # Relation
        sa.Column("relation_type", sa.String(50), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="1.0"),
        # Provenance
        sa.Column("relation_source", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("is_inferred", sa.Boolean(), nullable=False, server_default="false"),
        # Contraintes
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_type", "source_id",
            "target_type", "target_id",
            "relation_type",
            name="uq_graph_relation",
        ),
    )

    # Index standards
    op.create_index("ix_graph_relations_is_deleted", "graph_relations", ["is_deleted"])
    op.create_index("ix_graph_relations_source_type", "graph_relations", ["source_type"])
    op.create_index("ix_graph_relations_source_id", "graph_relations", ["source_id"])
    op.create_index("ix_graph_relations_target_type", "graph_relations", ["target_type"])
    op.create_index("ix_graph_relations_target_id", "graph_relations", ["target_id"])
    op.create_index("ix_graph_relations_relation_type", "graph_relations", ["relation_type"])
    op.create_index("ix_graph_relations_relation_source", "graph_relations", ["relation_source"])

    # Index composites pour les traversées fréquentes
    op.create_index(
        "ix_graph_source_lookup",
        "graph_relations",
        ["source_type", "source_id", "relation_type"],
    )
    op.create_index(
        "ix_graph_target_lookup",
        "graph_relations",
        ["target_type", "target_id", "relation_type"],
    )
    # Index partiel sur les relations non-supprimées avec confidence >= 0.5
    op.execute(
        "CREATE INDEX ix_graph_high_confidence ON graph_relations "
        "(source_id, target_id) "
        "WHERE is_deleted = false AND confidence_score >= 0.5"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_graph_high_confidence")
    op.drop_index("ix_graph_target_lookup", table_name="graph_relations")
    op.drop_index("ix_graph_source_lookup", table_name="graph_relations")
    op.drop_index("ix_graph_relations_relation_source", table_name="graph_relations")
    op.drop_index("ix_graph_relations_relation_type", table_name="graph_relations")
    op.drop_index("ix_graph_relations_target_id", table_name="graph_relations")
    op.drop_index("ix_graph_relations_target_type", table_name="graph_relations")
    op.drop_index("ix_graph_relations_source_id", table_name="graph_relations")
    op.drop_index("ix_graph_relations_source_type", table_name="graph_relations")
    op.drop_index("ix_graph_relations_is_deleted", table_name="graph_relations")
    op.drop_table("graph_relations")
