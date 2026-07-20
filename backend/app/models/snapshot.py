"""
Atlas - Snapshot Models
=======================
Historique immuable des prix et des scores — la matière première de la
boucle de calibration (Sprint 10 : « les scores élevés ont-ils été suivis
d'un mouvement ? »).

Décisions de conception :
- IMMUABLE : contrairement à opportunity_scores (une ligne active par
  entreprise, écrasée à chaque recalcul), ces tables ne font qu'accumuler.
  On n'update jamais un snapshot, on n'en soft-delete jamais un — c'est un
  journal de bord. Le soft delete hérité d'AtlasBase existe mais n'est
  utilisé par aucun code.
- captured_at est LA colonne d'analyse (l'axe temps de la calibration) ;
  created_at reste le timestamp technique d'insertion.
- ScoreSnapshot copie les champs du score (valeur, conviction, stage,
  version, composants) plutôt que de référencer opportunity_scores :
  la ligne vivante étant écrasée, seule une copie garantit l'historique.
- price est Numeric(18, 6) : les penny stocks européens cotent sous 1 €
  avec 4-6 décimales significatives ; un float perdrait de la précision.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AtlasBase


class PriceSnapshot(AtlasBase):
    """Photo d'un cours à un instant donné, pour une entreprise."""

    __tablename__ = "price_snapshots"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    price: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    market_cap: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    source: Mapped[str] = mapped_column(String(30), nullable=False, default="yfinance")
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class ScoreSnapshot(AtlasBase):
    """Copie figée du score Atlas d'une entreprise à un instant donné."""

    __tablename__ = "score_snapshots"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    score: Mapped[int] = mapped_column(Integer, nullable=False)
    conviction: Mapped[str] = mapped_column(String(20), nullable=False)
    stage: Mapped[str] = mapped_column(String(20), nullable=False)
    scoring_version: Mapped[int] = mapped_column(Integer, nullable=False)
    components: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
