"""
Atlas - Company Model
=====================
Une entreprise est l'entité centrale d'Atlas.

Toute l'intelligence du système gravite autour des entreprises :
événements, scores, graphe de connaissance, stories, alertes.

Décisions de conception :
- ISIN et ticker sont nullable : Atlas couvre aussi les entreprises privées
- Le champ `slug` est généré automatiquement pour les URLs propres
- `data_sources` (JSON) préserve la traçabilité des données (principe fondamental Atlas)
- Les relations futures (Themes, Events, Score...) sont annotées mais non implémentées
  — elles seront ajoutées dans leurs modules respectifs via `relationship()` back-populates
- market_cap est en USD cents (integer) pour éviter les problèmes de virgule flottante
"""

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AtlasBase


class CompanyStatus(StrEnum):
    """Statut opérationnel de l'entreprise."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ACQUIRED = "acquired"          # Rachetée — conservée pour l'historique
    BANKRUPT = "bankrupt"          # En faillite — conservée pour le ML
    MERGED = "merged"              # Fusionnée


class CompanyType(StrEnum):
    """Type d'entreprise selon son accès aux marchés publics."""

    PUBLIC = "public"              # Cotée en bourse
    PRIVATE = "private"            # Non cotée
    ETF = "etf"                    # Fonds indiciel coté
    SPAC = "spac"                  # Special Purpose Acquisition Company


class Company(AtlasBase):
    """
    Représente une entreprise dans l'univers Atlas.

    Relations implémentées :
    - themes: list["Theme"]              — Module 03 Theme Engine (Many-to-Many)

    Relations futures (non implémentées dans le Module 02) :
    - technologies: list["Technology"]   — Module 04 Knowledge Graph
    - events: list["Event"]              — Module 03 Event Engine
    - opportunity_scores: list["OpportunityScore"] — Module 05 Opportunity Engine
    - stories: list["Story"]             — Module 06 Stories Engine
    - graph_node_id: str                 — Module 04 (identifiant Neo4j)
    """

    __tablename__ = "companies"

    # ── Identité ───────────────────────────────────────────────────────────────

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Nom officiel de l'entreprise",
    )
    slug: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        unique=True,
        index=True,
        comment="Identifiant URL-friendly généré depuis le nom (ex: nvidia-corporation)",
    )
    legal_name: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Raison sociale complète si différente du nom commercial",
    )

    # ── Identifiants de marché ─────────────────────────────────────────────────

    ticker: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        comment="Symbole boursier (ex: NVDA, AAPL). Null pour les entreprises privées.",
    )
    isin: Mapped[str | None] = mapped_column(
        String(12),
        nullable=True,
        unique=True,
        index=True,
        comment="International Securities Identification Number (12 caractères)",
    )
    exchange: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Bourse de cotation principale (ex: NASDAQ, NYSE, EURONEXT)",
    )
    cusip: Mapped[str | None] = mapped_column(
        String(9),
        nullable=True,
        comment="Committee on Uniform Securities Identification Procedures (USA)",
    )

    # ── Classification ─────────────────────────────────────────────────────────

    company_type: Mapped[CompanyType] = mapped_column(
        Enum(CompanyType, name="company_type_enum"),
        nullable=False,
        default=CompanyType.PUBLIC,
        index=True,
        comment="Type d'entreprise : public, private, etf, spac",
    )
    status: Mapped[CompanyStatus] = mapped_column(
        Enum(CompanyStatus, name="company_status_enum"),
        nullable=False,
        default=CompanyStatus.ACTIVE,
        index=True,
        comment="Statut opérationnel de l'entreprise",
    )
    sector: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Secteur économique (ex: Technology, Healthcare, Energy)",
    )
    industry: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
        index=True,
        comment="Industrie précise (ex: Semiconductors, Biotechnology, Oil & Gas)",
    )
    sic_code: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="Standard Industrial Classification code (SEC)",
    )

    # ── Géographie ─────────────────────────────────────────────────────────────

    country: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
        index=True,
        comment="Code pays ISO 3166-1 alpha-2 (ex: US, FR, TW)",
    )
    country_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Nom complet du pays",
    )
    headquarters_city: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Ville du siège social",
    )
    headquarters_state: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="État / Région du siège social",
    )

    # ── Description ────────────────────────────────────────────────────────────

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Description de l'activité de l'entreprise",
    )
    description_short: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Description courte pour les previews (max 500 caractères)",
    )
    website: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="Site web officiel",
    )
    logo_url: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="URL du logo de l'entreprise",
    )

    # ── Données financières ────────────────────────────────────────────────────

    founded_year: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Année de fondation",
    )
    ipo_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Date d'introduction en bourse",
    )
    market_cap_usd: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        index=True,
        comment="Capitalisation boursière en USD (en milliers, pour éviter les floats)",
    )
    employees: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Nombre d'employés (approximatif)",
    )
    revenue_usd: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Revenu annuel en USD (en milliers)",
    )

    # ── Scores Atlas (calculés par les moteurs futurs) ─────────────────────────
    # Ces champs sont intentionnellement dénormalisés ici pour des raisons de
    # performance : les requêtes de liste n'ont pas besoin de joindre la table des scores.
    # La table des scores détaillée sera dans le Module 05 (Opportunity Engine).

    atlas_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Score de conviction Atlas (0-100). Calculé par l'Opportunity Engine.",
    )
    is_featured: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Entreprise mise en avant dans le dashboard Atlas",
    )

    # ── Traçabilité des données (principe fondamental Atlas) ───────────────────

    data_sources: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment=(
            "Sources des données : {source: url, last_updated: datetime}. "
            "Atlas ne modifie jamais une donnée sans tracer sa provenance."
        ),
    )
    last_enriched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Dernière fois que les données ont été enrichies par un collecteur",
    )

    # ── Tags libres ────────────────────────────────────────────────────────────

    tags: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment="Tags libres pour la recherche et le filtrage (ex: ['AI', 'defense', 'small-cap'])",
    )

    # ── Relations ──────────────────────────────────────────────────────────────

    themes: Mapped[list["Theme"]] = relationship(  # type: ignore[name-defined]
        "Theme",
        secondary="company_themes",
        back_populates="companies",
        lazy="select",
    )
    events: Mapped[list["Event"]] = relationship(  # type: ignore[name-defined]
        "Event",
        back_populates="company",
        lazy="select",
    )
    opportunity_score: Mapped["OpportunityScore | None"] = relationship(  # type: ignore[name-defined]
        "OpportunityScore",
        uselist=False,
        lazy="select",
        viewonly=True,
    )

    def __repr__(self) -> str:
        ticker_str = f" [{self.ticker}]" if self.ticker else ""
        return f"<Company {self.name}{ticker_str} ({self.country})>"
