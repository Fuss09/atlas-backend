"""
Atlas - Theme Model
====================
Un thème représente une tendance d'investissement transversale.

Exemples : Artificial Intelligence, Quantum Computing, Cybersecurity...

Une entreprise peut appartenir à plusieurs thèmes.
Un thème regroupe plusieurs entreprises.
→ Relation Many-to-Many via table d'association `company_themes`.

Décisions de conception :
- La table d'association porte `added_at` et `added_by` pour l'audit trail
- `maturity_level` permet de filtrer les thèmes par stade de développement
- `color` et `icon` sont stockés pour le frontend (pas de logique métier associée)
- Soft delete sur Theme uniquement — la table d'association est purgée physiquement
  (conserver l'historique des associations n'a pas de valeur ML dans ce cas)
- Relations futures annotées : Technologies, Events, OpportunityScore, Stories
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.base import AtlasBase


class MaturityLevel(StrEnum):
    """
    Stade de maturité d'un thème d'investissement.

    EMERGING  : Technologie/tendance naissante, risque élevé, potentiel maximal
    GROWTH    : Adoption en cours, croissance rapide, ratio risque/rendement optimal
    MATURE    : Marché établi, croissance stable, moins de volatilité
    """

    EMERGING = "emerging"
    GROWTH = "growth"
    MATURE = "mature"


# ─── Table d'association Company <-> Theme ────────────────────────────────────
#
# Utilisation d'une Table SQLAlchemy explicite (pas un modèle AtlasBase) car :
# 1. La table d'association n'a pas besoin d'UUID propre ni de soft delete
# 2. Elle porte uniquement des métadonnées légères (added_at, added_by)
# 3. Les suppressions sont physiques (pas d'historique ML requis ici)
#
# Si l'association devait porter plus de données (score de pertinence, source, etc.),
# elle deviendrait un modèle AtlasBase à part entière (pattern "association object").

company_themes = Table(
    "company_themes",
    Base.metadata,
    Column(
        "company_id",
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "theme_id",
        UUID(as_uuid=True),
        ForeignKey("themes.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "added_at",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
    Column(
        "added_by",
        UUID(as_uuid=True),
        nullable=True,
        comment="UUID de l'utilisateur ayant créé l'association",
    ),
)


class Theme(AtlasBase):
    """
    Thème d'investissement Atlas.

    Relations implémentées dans ce module :
    - companies : list[Company] via company_themes (Many-to-Many)

    Relations futures (non implémentées) :
    - technologies: list["Technology"]   — Module 04 Knowledge Graph
    - events: list["Event"]              — Module 03 Event Engine
    - opportunity_scores: list["OpportunityScore"] — Module 05
    - stories: list["Story"]             — Module 06
    """

    __tablename__ = "themes"

    # ── Identité ───────────────────────────────────────────────────────────────

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        unique=True,
        index=True,
        comment="Nom du thème (ex: Artificial Intelligence)",
    )
    slug: Mapped[str] = mapped_column(
        String(180),
        nullable=False,
        unique=True,
        index=True,
        comment="Identifiant URL-friendly (ex: artificial-intelligence)",
    )

    # ── Contenu ────────────────────────────────────────────────────────────────

    description: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
        comment="Description du thème et de sa pertinence pour les investisseurs",
    )
    category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Catégorie de regroupement (ex: Technology, Energy, Healthcare)",
    )
    maturity_level: Mapped[MaturityLevel] = mapped_column(
        String(20),
        nullable=False,
        default=MaturityLevel.EMERGING,
        index=True,
        comment="Stade de maturité : emerging, growth, mature",
    )

    # ── Présentation frontend ──────────────────────────────────────────────────

    color: Mapped[str | None] = mapped_column(
        String(7),
        nullable=True,
        comment="Couleur hexadécimale pour le frontend (ex: #6366f1)",
    )
    icon: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Nom de l'icône (ex: cpu, shield, zap) — référence à une lib d'icônes",
    )

    # ── Statut ─────────────────────────────────────────────────────────────────

    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        index=True,
        comment="Un thème inactif est masqué du frontend mais conservé en base",
    )

    # ── Relation Many-to-Many ──────────────────────────────────────────────────

    companies: Mapped[list["Company"]] = relationship(  # type: ignore[name-defined]
        "Company",
        secondary=company_themes,
        back_populates="themes",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Theme {self.name!r} [{self.maturity_level}]>"
