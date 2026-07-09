"""
Atlas - Discovery Models
========================
Modèles pour le Discovery Engine.

DiscoveryJob : trace chaque exécution d'un collecteur.
DiscoverySource : garde l'historique de provenance de chaque entreprise
  (une Company peut avoir été découverte par plusieurs sources successives).

Décisions de conception :
- Un DiscoveryJob est lié à une source (SEC, GitHub…) et produit un résultat mesurable.
- Les erreurs sont stockées en JSONB pour une inspection facile sans parse de logs.
- DiscoverySource est la table de jonction enrichie entre Company et une source externe.
  Elle porte l'identifiant de la source (ex: CIK pour SEC, org name pour GitHub)
  pour permettre les mises à jour incrémentales futures.
- Pas de soft delete sur DiscoveryJob — c'est un log immuable.
  On ne supprime jamais un historique de run.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.base import AtlasBase, TimestampMixin


class DiscoverySourceName(StrEnum):
    """
    Identifiants canoniques des sources de découverte.
    Ajouter une entrée ici pour enregistrer un nouveau collecteur.
    """

    SEC = "sec"                    # EDGAR — entreprises cotées US
    GITHUB = "github"              # Organisations open source actives
    YCOMBINATOR = "ycombinator"    # Startups YC (via API publique)
    CRUNCHBASE = "crunchbase"      # Startups & scale-ups (API payante)
    # ── Futurs collecteurs (non implémentés) ──────────────────────────────────
    FDA = "fda"                    # Approbations médicaments & dispositifs
    USPTO = "uspto"                # Dépôts de brevets
    ARXIV = "arxiv"                # Pré-publications scientifiques
    HUGGINGFACE = "huggingface"    # Modèles & datasets IA publiés
    PRODUCTHUNT = "producthunt"    # Lancements de produits
    APPSTORE = "appstore"          # Apps iOS
    GOOGLEPLAY = "googleplay"      # Apps Android
    PITCHBOOK = "pitchbook"        # Levées de fonds (API payante)


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"       # Terminé avec des erreurs non fatales
    FAILED = "failed"


class DiscoveryJob(Base, TimestampMixin):
    """
    Trace l'exécution d'un collecteur.
    Table de log immuable — pas de soft delete, pas d'AtlasBase.
    Chaque run crée une nouvelle entrée.
    """

    __tablename__ = "discovery_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Nom canonique du collecteur (ex: sec, github)",
    )
    status: Mapped[JobStatus] = mapped_column(
        String(20),
        nullable=False,
        default=JobStatus.PENDING,
        index=True,
    )
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="UUID de l'utilisateur ayant déclenché le job (null = automatique)",
    )

    # ── Résultats ──────────────────────────────────────────────────────────────
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    companies_found: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Nombre total d'entrées récupérées depuis la source",
    )
    companies_created: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Nouvelles entreprises créées en base",
    )
    companies_updated: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Entreprises existantes mises à jour",
    )
    companies_skipped: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Entrées ignorées (doublons, données insuffisantes)",
    )

    # ── Diagnostics ────────────────────────────────────────────────────────────
    errors: Mapped[list | None] = mapped_column(
        JSONB, nullable=True,
        comment="Liste des erreurs non fatales rencontrées pendant le run",
    )
    params: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="Paramètres passés au collecteur (limit, filters…)",
    )
    meta: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="Métadonnées spécifiques à la source (ex: SEC next_cursor)",
    )

    # ── Relation ───────────────────────────────────────────────────────────────
    discovery_sources: Mapped[list["DiscoverySource"]] = relationship(
        back_populates="job", lazy="select"
    )

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None

    def __repr__(self) -> str:
        return f"<DiscoveryJob source={self.source} status={self.status}>"


class DiscoverySource(Base, TimestampMixin):
    """
    Enregistre la provenance d'une entreprise depuis une source externe.

    Une entreprise peut avoir plusieurs DiscoverySources :
    - découverte via SEC en janvier
    - enrichie via GitHub en mars
    - confirmée via Crunchbase en juin

    Cette table est la pièce maîtresse de la traçabilité des données Atlas :
    chaque modification d'une Company via un collecteur est tracée ici.
    """

    __tablename__ = "discovery_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("discovery_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    external_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Identifiant de l'entité dans la source externe (ex: CIK SEC, GitHub org name)",
    )
    external_url: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="URL de la fiche source originale",
    )
    raw_data: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="Données brutes reçues depuis la source (pour retraitement futur)",
    )
    action: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="created",
        comment="Action effectuée : created, updated, skipped",
    )

    # ── Relations ──────────────────────────────────────────────────────────────
    company: Mapped["Company"] = relationship(lazy="select")  # type: ignore[name-defined]
    job: Mapped["DiscoveryJob"] = relationship(back_populates="discovery_sources", lazy="select")

    def __repr__(self) -> str:
        return f"<DiscoverySource source={self.source} company_id={self.company_id}>"
