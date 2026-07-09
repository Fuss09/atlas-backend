"""Module 03 — Create themes table and company_themes association

Revision ID: 003_themes
Revises: 002_companies
Create Date: 2025-01-03 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003_themes"
down_revision: str | None = "002_companies"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Table themes ───────────────────────────────────────────────────────────
    op.create_table(
        "themes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("slug", sa.String(180), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("maturity_level", sa.String(20), nullable=False, server_default="emerging"),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_themes_name"),
        sa.UniqueConstraint("slug", name="uq_themes_slug"),
    )

    op.create_index("ix_themes_is_deleted", "themes", ["is_deleted"])
    op.create_index("ix_themes_name", "themes", ["name"])
    op.create_index("ix_themes_slug", "themes", ["slug"])
    op.create_index("ix_themes_category", "themes", ["category"])
    op.create_index("ix_themes_maturity_level", "themes", ["maturity_level"])
    op.create_index("ix_themes_is_active", "themes", ["is_active"])

    # Index trigram sur le nom des thèmes
    op.execute(
        "CREATE INDEX ix_themes_name_trgm ON themes "
        "USING gin (name gin_trgm_ops)"
    )

    # ── Table d'association company_themes ─────────────────────────────────────
    op.create_table(
        "company_themes",
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "theme_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("themes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "added_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    op.create_index("ix_company_themes_company_id", "company_themes", ["company_id"])
    op.create_index("ix_company_themes_theme_id", "company_themes", ["theme_id"])

    # ── Données initiales : thèmes Atlas de référence ─────────────────────────
    op.execute("""
        INSERT INTO themes (id, name, slug, description, category, maturity_level, color, icon, is_active)
        VALUES
            (gen_random_uuid(), 'Artificial Intelligence', 'artificial-intelligence',
             'Entreprises développant ou déployant des modèles IA, du machine learning et des systèmes autonomes.',
             'Technology', 'growth', '#6366f1', 'cpu', true),
            (gen_random_uuid(), 'Quantum Computing', 'quantum-computing',
             'Technologies quantiques appliquées au calcul, à la cryptographie et à l''optimisation.',
             'Technology', 'emerging', '#8b5cf6', 'zap', true),
            (gen_random_uuid(), 'Cybersecurity', 'cybersecurity',
             'Protection des systèmes d''information, détection des menaces et réponse aux incidents.',
             'Technology', 'growth', '#ef4444', 'shield', true),
            (gen_random_uuid(), 'Semiconductors', 'semiconductors',
             'Conception et fabrication de puces électroniques, fonderies et équipements de lithographie.',
             'Technology', 'mature', '#f59e0b', 'circuit-board', true),
            (gen_random_uuid(), 'Defense & Aerospace', 'defense-aerospace',
             'Systèmes de défense, drones militaires, renseignement et technologies duales.',
             'Defense', 'mature', '#64748b', 'target', true),
            (gen_random_uuid(), 'Biotechnology', 'biotechnology',
             'Thérapies géniques, édition du génome, diagnostics moléculaires et biologie synthétique.',
             'Healthcare', 'growth', '#10b981', 'dna', true),
            (gen_random_uuid(), 'Space', 'space',
             'Lanceurs, satellites, exploration spatiale et économie orbitale basse.',
             'Aerospace', 'emerging', '#0ea5e9', 'rocket', true),
            (gen_random_uuid(), 'Energy Transition', 'energy-transition',
             'Énergies renouvelables, stockage d''énergie, hydrogène vert et réseaux intelligents.',
             'Energy', 'growth', '#22c55e', 'sun', true),
            (gen_random_uuid(), 'Nuclear Energy', 'nuclear-energy',
             'Réacteurs SMR, fusion nucléaire et infrastructure de production d''énergie bas-carbone.',
             'Energy', 'emerging', '#f97316', 'atom', true),
            (gen_random_uuid(), 'Robotics & Automation', 'robotics-automation',
             'Robots industriels, cobots, automatisation des entrepôts et robotique chirurgicale.',
             'Technology', 'growth', '#a855f7', 'bot', true),
            (gen_random_uuid(), 'Cloud Computing', 'cloud-computing',
             'Infrastructure cloud, SaaS, edge computing et hyperscalers.',
             'Technology', 'mature', '#3b82f6', 'cloud', true),
            (gen_random_uuid(), 'Autonomous Driving', 'autonomous-driving',
             'Véhicules autonomes, LiDAR, logiciels de conduite et infrastructure V2X.',
             'Transportation', 'emerging', '#ec4899', 'car', true)
    """)


def downgrade() -> None:
    op.drop_index("ix_company_themes_theme_id", table_name="company_themes")
    op.drop_index("ix_company_themes_company_id", table_name="company_themes")
    op.drop_table("company_themes")

    op.execute("DROP INDEX IF EXISTS ix_themes_name_trgm")
    op.drop_index("ix_themes_is_active", table_name="themes")
    op.drop_index("ix_themes_maturity_level", table_name="themes")
    op.drop_index("ix_themes_category", table_name="themes")
    op.drop_index("ix_themes_slug", table_name="themes")
    op.drop_index("ix_themes_name", table_name="themes")
    op.drop_index("ix_themes_is_deleted", table_name="themes")
    op.drop_table("themes")
