"""
Atlas - Snapshot Schemas
========================
Contrats de lecture de l'historique prix/scores.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PriceSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    price: float
    currency: str
    volume: int | None
    market_cap: int | None
    source: str
    captured_at: datetime


class ScoreSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    score: int
    conviction: str
    stage: str
    scoring_version: int
    captured_at: datetime
