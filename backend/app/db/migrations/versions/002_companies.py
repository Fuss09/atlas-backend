"""Module 02 — Create companies table

Revision ID: 002_companies
Revises: 001_initial
Create Date: 2025-01-02 00:00:00.000000

Décisions de migration :
- Deux nouveaux enums : company_type_enum, company_status_enum
- Index sur les colonnes fréquemment filtrées (sector, country, status, ticker)
- Index trigram (GIN) sur name pour la recherche ILIKE performante
  (nécessite l'extension pg_trgm activée dans init.sql)
- JSONB pour data_sources et tags (flexibilité sans migration pour les métadonnées)
- market_cap_usd et revenue_usd en BIGINT (USD en milliers, évite les floats)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002_companies"
down_revision: str | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Enums ──────────────────────────────────────────────────────────────────
    op.execute(
        "CREATE TYPE company_type_enum AS ENUM "
        "('public', 'private', 'etf', 'spac')"
    )
    op.execute(
        "CREATE TYPE company_status_enum AS ENUM "
        "('active', 'inactive', 'acquired', 'bankrupt', 'merged')"
    )

    # ── Table companies ────────────────────────────────────────────────────────
    op.create_table(
        "companies",
        # ── Identité de base AtlasBase ─────────────────────────────────────
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),

        # ── Identité ──────────────────────────────────────────────────────
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(300), nullable=False),
        sa.Column("legal_name", sa.String(500), nullable=True),

        # ── Identifiants de marché ────────────────────────────────────────
        sa.Column("ticker", sa.String(20), nullable=True),
        sa.Column("isin", sa.String(12), nullable=True),
        sa.Column("exchange", sa.String(50), nullable=True),
        sa.Column("cusip", sa.String(9), nullable=True),

        # ── Classification ────────────────────────────────────────────────
        sa.Column(
            "company_type",
            postgresql.ENUM("public", "private", "etf", "spac", name="company_type_enum", create_type=False),
            nullable=False,
            server_default="public",
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "active", "inactive", "acquired", "bankrupt", "merged",
                name="company_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column("sector", sa.String(100), nullable=True),
        sa.Column("industry", sa.String(150), nullable=True),
        sa.Column("sic_code", sa.String(10), nullable=True),

        # ── Géographie ────────────────────────────────────────────────────
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("country_name", sa.String(100), nullable=True),
        sa.Column("headquarters_city", sa.String(100), nullable=True),
        sa.Column("headquarters_state", sa.String(100), nullable=True),

        # ── Description ───────────────────────────────────────────────────
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("description_short", sa.String(500), nullable=True),
        sa.Column("website", sa.String(512), nullable=True),
        sa.Column("logo_url", sa.String(512), nullable=True),

        # ── Données financières ───────────────────────────────────────────
        sa.Column("founded_year", sa.Integer(), nullable=True),
        sa.Column("ipo_date", sa.Date(), nullable=True),
        sa.Column("market_cap_usd", sa.BigInteger(), nullable=True),
        sa.Column("employees", sa.Integer(), nullable=True),
        sa.Column("revenue_usd", sa.BigInteger(), nullable=True),

        # ── Scores Atlas ──────────────────────────────────────────────────
        sa.Column("atlas_score", sa.Integer(), nullable=True),
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default="false"),

        # ── Traçabilité ───────────────────────────────────────────────────
        sa.Column("data_sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_enriched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),

        sa.PrimaryKeyConstraint("id"),
    )

    # ── Index standards ────────────────────────────────────────────────────────
    op.create_index("ix_companies_is_deleted", "companies", ["is_deleted"])
    op.create_index("ix_companies_name", "companies", ["name"])
    op.create_index("ix_companies_slug", "companies", ["slug"], unique=True)
    op.create_index("ix_companies_ticker", "companies", ["ticker"])
    op.create_index("ix_companies_isin", "companies", ["isin"], unique=True,
                    postgresql_where=sa.text("isin IS NOT NULL"))
    op.create_index("ix_companies_sector", "companies", ["sector"])
    op.create_index("ix_companies_industry", "companies", ["industry"])
    op.create_index("ix_companies_country", "companies", ["country"])
    op.create_index("ix_companies_company_type", "companies", ["company_type"])
    op.create_index("ix_companies_status", "companies", ["status"])
    op.create_index("ix_companies_market_cap_usd", "companies", ["market_cap_usd"])
    op.create_index("ix_companies_atlas_score", "companies", ["atlas_score"])
    op.create_index("ix_companies_is_featured", "companies", ["is_featured"])

    # ── Index GIN pour la recherche trigram ────────────────────────────────────
    # Accélère les requêtes ILIKE sur le nom (requiert pg_trgm activé dans init.sql)
    op.execute(
        "CREATE INDEX ix_companies_name_trgm ON companies "
        "USING gin (name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_companies_description_short_trgm ON companies "
        "USING gin (description_short gin_trgm_ops) "
        "WHERE description_short IS NOT NULL"
    )

    # ── Index GIN pour les JSONB ───────────────────────────────────────────────
    op.execute(
        "CREATE INDEX ix_companies_tags_gin ON companies USING gin (tags) "
        "WHERE tags IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_companies_tags_gin")
    op.execute("DROP INDEX IF EXISTS ix_companies_description_short_trgm")
    op.execute("DROP INDEX IF EXISTS ix_companies_name_trgm")
    op.drop_index("ix_companies_is_featured", table_name="companies")
    op.drop_index("ix_companies_atlas_score", table_name="companies")
    op.drop_index("ix_companies_market_cap_usd", table_name="companies")
    op.drop_index("ix_companies_status", table_name="companies")
    op.drop_index("ix_companies_company_type", table_name="companies")
    op.drop_index("ix_companies_country", table_name="companies")
    op.drop_index("ix_companies_industry", table_name="companies")
    op.drop_index("ix_companies_sector", table_name="companies")
    op.drop_index("ix_companies_isin", table_name="companies")
    op.drop_index("ix_companies_ticker", table_name="companies")
    op.drop_index("ix_companies_slug", table_name="companies")
    op.drop_index("ix_companies_name", table_name="companies")
    op.drop_index("ix_companies_is_deleted", table_name="companies")
    op.drop_table("companies")
    op.execute("DROP TYPE IF EXISTS company_status_enum")
    op.execute("DROP TYPE IF EXISTS company_type_enum")
