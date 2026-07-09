"""
Atlas - Event Service
=====================
Logique métier pour les events.

Deux chemins de création :
1. Manuel  : via l'API (analyst/admin) → EventCreate
2. Automatique : appelé par le Discovery Engine après collecte → create_from_discovery()

Le service expose aussi les méthodes consommées par l'Opportunity Engine (Module 06) :
- get_unprocessed()        : events à scorer
- mark_processed_bulk()   : après calcul du score
- get_score_boost()        : contribution estimée d'un event au score
"""

import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AlreadyExistsError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.event import (
    EVENT_TYPE_SCORE_BOOST,
    IMPORTANCE_WEIGHTS,
    Event,
    EventType,
    ImportanceLevel,
)
from app.repositories.company import CompanyRepository
from app.repositories.event import EventRepository
from app.schemas.company import PaginatedResponse
from app.schemas.event import (
    EventCreate,
    EventListItem,
    EventResponse,
    EventSearchParams,
    EventStatsResponse,
    EventUpdate,
)

logger = get_logger(__name__)


def _compute_score_boost(event_type: EventType, importance: ImportanceLevel, confidence: float) -> float:
    """
    Calcule la contribution estimée d'un event au score Atlas.
    Formule : boost_type × poids_importance × confiance
    Exposé ici pour que l'Opportunity Engine puisse l'importer directement.
    """
    base = EVENT_TYPE_SCORE_BOOST.get(event_type, 1.0)
    weight = IMPORTANCE_WEIGHTS.get(importance, 0.5)
    return round(base * weight * confidence, 2)


class EventService:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = EventRepository(session)
        self.company_repo = CompanyRepository(session)

    # ── Lecture ────────────────────────────────────────────────────────────────

    async def get_by_id(self, event_id: uuid.UUID) -> Event:
        event = await self.repo.get_by_id(event_id)
        if not event:
            raise NotFoundError("Event", event_id)
        return event

    async def list_events(
        self,
        params: EventSearchParams,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse[EventListItem]:
        offset = (page - 1) * page_size
        events, total = await asyncio.gather(
            self.repo.search(params, offset=offset, limit=page_size),
            self.repo.count_search(params),
        )

        # Batch-fetch companies for this page only — avoids an N+1 while
        # keeping the cost bounded to page_size, same pattern used by
        # OpportunityScoreService.list_opportunities.
        companies_by_id = {}
        if events:
            company_ids = list({e.company_id for e in events})
            companies = await self.company_repo.get_by_ids(company_ids)
            companies_by_id = {c.id: c for c in companies}

        items = []
        for e in events:
            company = companies_by_id.get(e.company_id)
            item = EventListItem.model_validate(e)
            item.company_name = company.name if company else "Unknown"
            item.company_slug = company.slug if company else ""
            item.company_ticker = company.ticker if company else None
            items.append(item)

        return PaginatedResponse[EventListItem](
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_company_events(
        self,
        company_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse[EventListItem]:
        company = await self.company_repo.get_by_id(company_id)
        if not company:
            raise NotFoundError("Company", company_id)
        offset = (page - 1) * page_size
        events, total = await asyncio.gather(
            self.repo.get_for_company(company_id, limit=page_size, offset=offset),
            self.repo.count_for_company(company_id),
        )
        items = []
        for e in events:
            item = EventListItem.model_validate(e)
            item.company_name = company.name
            item.company_slug = company.slug
            item.company_ticker = company.ticker
            items.append(item)
        return PaginatedResponse[EventListItem](
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_stats(self, company_id: uuid.UUID) -> EventStatsResponse:
        company = await self.company_repo.get_by_id(company_id)
        if not company:
            raise NotFoundError("Company", company_id)
        stats = await self.repo.get_stats_for_company(company_id)
        # Calcul du boost estimé total
        events = await self.repo.get_for_company(company_id, limit=1000)
        total_boost = sum(
            _compute_score_boost(e.event_type, e.importance, e.confidence_score)
            for e in events
            if not e.is_deleted
        )
        return EventStatsResponse(
            company_id=company_id,
            total_events=stats["total"],
            unprocessed_events=stats["unprocessed"],
            by_type=stats["by_type"],
            by_importance=stats["by_importance"],
            latest_occurred_at=stats["latest"],
            estimated_score_boost=round(min(total_boost, 100.0), 2),
        )

    # ── Écriture ───────────────────────────────────────────────────────────────

    async def create(
        self,
        data: EventCreate,
        created_by: uuid.UUID | None = None,
    ) -> EventResponse:
        company = await self.company_repo.get_by_id(data.company_id)
        if not company:
            raise NotFoundError("Company", data.company_id)

        # Déduplication par source_id
        if data.source_id and await self.repo.source_id_exists(data.source, data.source_id):
            raise AlreadyExistsError("Event", "source_id", data.source_id)

        event = await self.repo.create(**data.model_dump())

        logger.info(
            "Event created",
            event_id=str(event.id),
            event_type=event.event_type,
            company_id=str(event.company_id),
            created_by=str(created_by) if created_by else "system",
        )
        return self._to_response(event)

    async def create_from_discovery(
        self,
        company_id: uuid.UUID,
        event_type: EventType,
        title: str,
        source: str,
        occurred_at: datetime | None = None,
        summary: str | None = None,
        source_url: str | None = None,
        source_id: str | None = None,
        importance: ImportanceLevel = ImportanceLevel.MEDIUM,
        confidence_score: float = 0.8,
        raw_data: dict | None = None,
    ) -> Event | None:
        """
        Crée un event depuis le Discovery Engine.
        Retourne None si l'event est un doublon (idempotent).
        Pas d'exception sur doublon — le Discovery Engine ne doit pas planter pour ça.
        """
        if source_id and await self.repo.source_id_exists(source, source_id):
            return None

        event = await self.repo.create(
            company_id=company_id,
            event_type=event_type,
            importance=importance,
            title=title,
            summary=summary,
            occurred_at=occurred_at or datetime.now(UTC),
            source=source,
            source_url=source_url,
            source_id=source_id,
            confidence_score=confidence_score,
            raw_data=raw_data or {},
        )
        logger.info(
            "Event created from discovery",
            event_type=event_type,
            company_id=str(company_id),
            source=source,
        )
        return event

    async def update(
        self,
        event_id: uuid.UUID,
        data: EventUpdate,
        updated_by: uuid.UUID | None = None,
    ) -> EventResponse:
        await self.get_by_id(event_id)
        updates = data.model_dump(exclude_none=True)
        if not updates:
            event = await self.get_by_id(event_id)
            return self._to_response(event)
        updated = await self.repo.update(event_id, **updates)
        if not updated:
            raise NotFoundError("Event", event_id)
        logger.info("Event updated", event_id=str(event_id), fields=list(updates.keys()))
        return self._to_response(updated)

    async def delete(self, event_id: uuid.UUID, deleted_by: uuid.UUID | None = None) -> None:
        success = await self.repo.soft_delete(event_id)
        if not success:
            raise NotFoundError("Event", event_id)
        logger.info("Event soft-deleted", event_id=str(event_id))

    # ── Interface Opportunity Engine (Module 06) ───────────────────────────────

    async def get_unprocessed(self, limit: int = 100) -> list[Event]:
        """Récupère les events à traiter par l'Opportunity Engine."""
        return await self.repo.get_unprocessed(limit=limit)

    async def mark_processed_bulk(
        self, event_ids: list[uuid.UUID], scoring_version: int = 1
    ) -> int:
        """Marque un batch d'events comme traités."""
        count = await self.repo.mark_processed_bulk(event_ids, scoring_version)
        logger.info("Events marked as processed", count=count, version=scoring_version)
        return count

    @staticmethod
    def get_score_boost(
        event_type: EventType,
        importance: ImportanceLevel,
        confidence: float,
    ) -> float:
        """Calcule la contribution d'un event au score — utilisé par l'Opportunity Engine."""
        return _compute_score_boost(event_type, importance, confidence)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _to_response(self, event: Event) -> EventResponse:
        response = EventResponse.model_validate(event)
        response.score_boost = _compute_score_boost(
            event.event_type, event.importance, event.confidence_score
        )
        return response
