"""
Atlas - Event Schemas
=====================
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.event import EventType, ImportanceLevel
from app.schemas.company import PaginatedResponse


class EventCreate(BaseModel):
    """Création manuelle d'un event (endpoint admin/analyst)."""

    company_id: uuid.UUID
    event_type: EventType
    importance: ImportanceLevel = ImportanceLevel.MEDIUM
    title: str = Field(min_length=3, max_length=500)
    summary: str | None = Field(default=None)
    occurred_at: datetime
    expires_at: datetime | None = None
    source: str = Field(min_length=1, max_length=50, default="manual")
    source_url: str | None = Field(default=None, max_length=512)
    source_id: str | None = Field(default=None, max_length=255)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    raw_data: dict[str, Any] | None = None


class EventUpdate(BaseModel):
    """Mise à jour partielle d'un event."""

    importance: ImportanceLevel | None = None
    title: str | None = Field(default=None, min_length=3, max_length=500)
    summary: str | None = None
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    sentiment_score: float | None = Field(default=None, ge=-1.0, le=1.0)
    expires_at: datetime | None = None


class EventResponse(BaseModel):
    """Représentation complète d'un event."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    event_type: EventType
    importance: ImportanceLevel
    title: str
    summary: str | None
    occurred_at: datetime
    expires_at: datetime | None
    source: str
    source_url: str | None
    source_id: str | None
    confidence_score: float
    sentiment_score: float | None
    is_processed: bool
    processing_version: int | None
    created_at: datetime
    updated_at: datetime

    # Calculé : contribution potentielle au score
    score_boost: float = 0.0


class EventListItem(BaseModel):
    """Version allégée pour les listes."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    company_name: str = "Unknown"
    company_slug: str = ""
    company_ticker: str | None = None
    event_type: EventType
    importance: ImportanceLevel
    title: str
    occurred_at: datetime
    source: str
    confidence_score: float
    is_processed: bool


class EventSearchParams(BaseModel):
    """Paramètres de recherche pour les events."""

    company_id: uuid.UUID | None = None
    event_type: EventType | None = None
    importance: ImportanceLevel | None = None
    source: str | None = None
    is_processed: bool | None = None
    occurred_after: datetime | None = None
    occurred_before: datetime | None = None
    q: str | None = Field(default=None, max_length=200, description="Recherche texte (titre, résumé)")


class EventStatsResponse(BaseModel):
    """Statistiques agrégées des events d'une entreprise."""

    company_id: uuid.UUID
    total_events: int
    unprocessed_events: int
    by_type: dict[str, int]
    by_importance: dict[str, int]
    latest_occurred_at: datetime | None
    estimated_score_boost: float
