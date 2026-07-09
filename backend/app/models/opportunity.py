"""
Atlas - Opportunity Score Model
=================================
Persistance du dernier score d'opportunité calculé pour chaque entreprise.

Décisions de conception :
- Une seule ligne "active" par entreprise (company_id unique) — le score est
  recalculé en place plutôt que de créer un historique de lignes.
  Choix motivé par la simplicité du MVP : le détail des events reste, lui,
  entièrement historisé (table `events`), donc rien n'est perdu — un futur
  historique de scores pourra être reconstruit en rejouant le moteur sur les
  events tels qu'ils étaient à une date donnée. Si un vrai historique de
  scores dans le temps devient nécessaire, ADR à part (voir docs/adr).
- components est stocké en JSONB : chaque composant (events, theme_strength,
  company_quality, discovery_signals, market_signals) y est sérialisé avec
  sa valeur, son poids et ses facteurs. Ce n'est pas relationnel car la forme
  des composants est amenée à évoluer (ex: ajout de Market Signals) sans
  vouloir migrer le schéma à chaque fois.
- positive_factors / negative_factors sont dupliqués à plat (hors JSONB) en
  plus du détail par composant, pour permettre un affichage rapide côté API
  sans reparser le JSONB.
- scoring_version : incrémenté à chaque changement de méthode de calcul.
  Permet de savoir, pour un score donné, avec quelle version de l'algorithme
  il a été produit — indispensable avant un futur passage au Machine Learning.
- Pas de soft delete : le score suit le cycle de vie de la Company elle-même.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.engines.opportunity import ConvictionLevel, OpportunityStage
from app.models.base import AtlasBase

# ConvictionLevel et OpportunityStage sont définis dans app.engines.opportunity
# (le moteur pur) et réutilisés ici pour la persistance : c'est le moteur qui
# fait autorité sur la sémantique du scoring, le modèle ne fait que la stocker.
__all__ = ["ConvictionLevel", "OpportunityStage", "OpportunityScore"]


class OpportunityScore(AtlasBase):
    """
    Dernier score d'opportunité calculé pour une entreprise.

    Relations :
    - company: Company (One-to-One via company_id unique)
    """

    __tablename__ = "opportunity_scores"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # ── Score global ─────────────────────────────────────────────────────────

    score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Score global d'opportunité, 0 à 100",
    )
    conviction: Mapped[ConvictionLevel] = mapped_column(
        String(20),
        nullable=False,
        comment="Niveau de conviction dérivé du score : low, moderate, high, very_high",
    )
    stage: Mapped[OpportunityStage] = mapped_column(
        String(20),
        nullable=False,
        comment="Stade de découverte de l'opportunité : early, acceleration, confirmation, mature",
    )
    stage_rationale: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Explication en une phrase du stade attribué",
    )

    # ── Détail explicable ────────────────────────────────────────────────────

    components: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Détail par composant : {name: {value, weight, positive_factors, negative_factors, is_connected}}",
    )
    positive_factors: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Facteurs positifs agrégés, à plat, pour affichage rapide",
    )
    negative_factors: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Facteurs négatifs agrégés, à plat, pour affichage rapide",
    )

    # ── Traçabilité du calcul ────────────────────────────────────────────────

    scoring_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Version de l'algorithme de scoring utilisée — voir OpportunityEngine.SCORING_VERSION",
    )
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Date du dernier calcul (peut différer de updated_at s'il n'y a pas eu de changement)",
    )

    def __repr__(self) -> str:
        return f"<OpportunityScore company_id={self.company_id} score={self.score}>"
