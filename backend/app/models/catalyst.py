"""
Atlas - Catalyst Model
======================
Un catalyseur est un événement FUTUR daté susceptible de faire bouger le cours
d'une entreprise : lecture de résultats d'essai clinique, publication de
résultats financiers, décision réglementaire, fin de lock-up...

C'est le miroir temporel de la table events : events regarde le passé
(ce qui s'est produit), catalysts regarde l'avenir (les rendez-vous connus).
Le cas d'usage fondateur : « Abivax publie sa phase 3 au T3 » — savoir que le
rendez-vous existe, avant qu'il arrive.

Décisions de conception :
- expected_date + date_precision : les registres publient des dates à
  précision variable (« 2026-09-15 », « September 2026 »). On stocke la date
  normalisée ET sa précision réelle — afficher « 15 sept. » quand la source
  ne donnait que « septembre » serait une fausse précision.
- external_id : clé de déduplication pour les sources automatiques
  (ex : « NCT05123456:pcd » pour la primary completion date d'un essai).
  Unique en base (les NULL multiples restent permis pour les manuels).
- status : upcoming → occurred/cancelled. Un catalyseur passé n'est pas
  supprimé — c'est de la matière pour la calibration (le mouvement post-
  catalyseur est exactement ce que le Track Record mesurera).
"""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AtlasBase


class Catalyst(AtlasBase):
    """Événement futur daté pouvant impacter une entreprise."""

    __tablename__ = "catalysts"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    catalyst_type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    expected_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    date_precision: Mapped[str] = mapped_column(String(10), nullable=False, default="day")

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="upcoming")

    source: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    external_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, unique=True
    )

    company = relationship("Company", lazy="joined")
