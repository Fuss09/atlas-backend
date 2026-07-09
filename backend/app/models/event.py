"""
Atlas - Event Model
====================
Un Event représente un signal discret détecté sur une entreprise.

Les events sont la matière première de l'Opportunity Engine (Module 06) :
c'est sur leur agrégation et pondération que le score Atlas sera calculé.

Décisions de conception :
- EventType couvre toutes les sources prévues — extensible via migration ALTER TYPE
- ImportanceLevel + confidence_score permettent la pondération dans l'Opportunity Engine
- occurred_at distinct de created_at : la date de l'événement vs la date d'ingestion
- source_url + raw_data : traçabilité totale, principe fondamental Atlas
- company_id obligatoire : un Event sans Company n'a pas de sens dans Atlas
- Soft delete : les events sont conservés pour le ML et le backtesting
- is_processed : flag pour l'Opportunity Engine (marque ce qu'il a déjà consommé)
- expires_at : certains events ont une durée de vie (ex: INSIDER_BUY sur 6 mois)
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AtlasBase


class EventType(StrEnum):
    # ── Marché & Actualités ────────────────────────────────────────────────────
    NEWS = "news"                         # Article de presse général
    EARNINGS = "earnings"                 # Publication de résultats financiers

    # ── Régulatoire US (SEC) ───────────────────────────────────────────────────
    SEC_FILING = "sec_filing"             # Dépôt réglementaire (10-K, 10-Q, 8-K…)
    INSIDER_BUY = "insider_buy"           # Achat d'initiés (Form 4)
    INSIDER_SELL = "insider_sell"         # Vente d'initiés (Form 4)

    # ── Santé & Biotech (FDA) ──────────────────────────────────────────────────
    FDA_APPROVAL = "fda_approval"         # Approbation d'un médicament ou dispositif
    FDA_REJECTION = "fda_rejection"       # Rejet ou Complete Response Letter
    CLINICAL_TRIAL = "clinical_trial"     # Nouvelle phase clinique démarrée

    # ── Produit & Business ─────────────────────────────────────────────────────
    PRODUCT_LAUNCH = "product_launch"     # Lancement d'un nouveau produit
    PARTNERSHIP = "partnership"           # Partenariat stratégique annoncé
    ACQUISITION = "acquisition"           # Acquisition ou fusion
    FUNDING = "funding"                   # Levée de fonds (Series A, B, C…)

    # ── Propriété Intellectuelle ───────────────────────────────────────────────
    PATENT = "patent"                     # Dépôt ou approbation de brevet (USPTO)

    # ── Open Source & Tech ────────────────────────────────────────────────────
    GITHUB_ACTIVITY = "github_activity"   # Pic d'activité GitHub significatif

    # ── Découverte Atlas ──────────────────────────────────────────────────────
    YC_DISCOVERY = "yc_discovery"         # Entreprise détectée via Y Combinator
    CRUNCHBASE_FUNDING = "crunchbase_funding"  # Levée détectée via Crunchbase


class ImportanceLevel(StrEnum):
    """
    Niveau d'importance d'un événement.
    Utilisé par l'Opportunity Engine pour la pondération des scores.

    LOW      : signal faible, contexte informatif (ex: article de blog)
    MEDIUM   : signal modéré, à surveiller (ex: partenariat commercial)
    HIGH     : signal fort, impact probable sur le business (ex: FDA approval)
    CRITICAL : signal majeur, impact immédiat attendu (ex: acquisition, IPO)
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Poids par importance — utilisés par l'Opportunity Engine (Module 06)
IMPORTANCE_WEIGHTS: dict[ImportanceLevel, float] = {
    ImportanceLevel.LOW: 0.25,
    ImportanceLevel.MEDIUM: 0.50,
    ImportanceLevel.HIGH: 0.75,
    ImportanceLevel.CRITICAL: 1.00,
}

# Boost de score par type d'event — base pour l'Opportunity Engine
EVENT_TYPE_SCORE_BOOST: dict[EventType, float] = {
    EventType.FDA_APPROVAL: 20.0,
    EventType.ACQUISITION: 15.0,
    EventType.FUNDING: 12.0,
    EventType.INSIDER_BUY: 10.0,
    EventType.PARTNERSHIP: 8.0,
    EventType.PRODUCT_LAUNCH: 7.0,
    EventType.EARNINGS: 6.0,
    EventType.PATENT: 5.0,
    EventType.YC_DISCOVERY: 5.0,
    EventType.CLINICAL_TRIAL: 8.0,
    EventType.CRUNCHBASE_FUNDING: 12.0,
    EventType.SEC_FILING: 3.0,
    EventType.GITHUB_ACTIVITY: 4.0,
    EventType.NEWS: 2.0,
    EventType.INSIDER_SELL: -5.0,        # Signal négatif
    EventType.FDA_REJECTION: -15.0,      # Signal fortement négatif
}


class Event(AtlasBase):
    """
    Événement détecté sur une entreprise.

    Cycle de vie :
    1. Créé par un collecteur (Discovery Engine) ou manuellement
    2. Consommé par l'Opportunity Engine (is_processed = True)
    3. Contribue au atlas_score de la Company

    Relations :
    - company: Company (Many-to-One, obligatoire)
    """

    __tablename__ = "events"

    # ── Entreprise liée ────────────────────────────────────────────────────────

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Classification ─────────────────────────────────────────────────────────

    event_type: Mapped[EventType] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    importance: Mapped[ImportanceLevel] = mapped_column(
        String(20),
        nullable=False,
        default=ImportanceLevel.MEDIUM,
        index=True,
    )

    # ── Contenu ────────────────────────────────────────────────────────────────

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Résumé synthétique de l'événement (généré ou extrait)",
    )

    # ── Temporalité ───────────────────────────────────────────────────────────

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Date réelle de l'événement (≠ created_at qui est la date d'ingestion)",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date d'expiration du signal (ex: INSIDER_BUY expire après 6 mois)",
    )

    # ── Source & Traçabilité ───────────────────────────────────────────────────

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Collecteur source (ex: sec, github, ycombinator, manual)",
    )
    source_url: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="URL de la source primaire",
    )
    source_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Identifiant de l'event dans la source (pour déduplication)",
    )
    raw_data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Données brutes de la source — jamais modifiées",
    )

    # ── Scoring ────────────────────────────────────────────────────────────────

    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        comment="Niveau de confiance dans l'exactitude des données (0.0 à 1.0)",
    )
    sentiment_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Score de sentiment (−1.0 négatif → +1.0 positif). Calculé par l'IA.",
    )

    # ── État de traitement ─────────────────────────────────────────────────────

    is_processed: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        index=True,
        comment="True quand l'Opportunity Engine a consommé et intégré cet event dans le score",
    )
    processing_version: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Version du moteur de scoring qui a traité cet event (pour retraitement)",
    )

    # ── Relation ───────────────────────────────────────────────────────────────

    company: Mapped["Company"] = relationship(  # type: ignore[name-defined]
        "Company",
        back_populates="events",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Event {self.event_type} [{self.importance}] company={self.company_id}>"
