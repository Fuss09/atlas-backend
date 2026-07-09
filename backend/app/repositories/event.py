"""
Atlas - Event Repository
========================
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event, EventType, ImportanceLevel
from app.repositories.base import BaseRepository
from app.schemas.event import EventSearchParams


class EventRepository(BaseRepository[Event]):

    model = Event

    # ── Lookups ────────────────────────────────────────────────────────────────

    async def get_by_source_id(self, source: str, source_id: str) -> Event | None:
        """Déduplication : retrouve un event par son identifiant source."""
        result = await self.session.execute(
            select(Event).where(
                Event.source == source,
                Event.source_id == source_id,
                Event.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    # ── Recherche ──────────────────────────────────────────────────────────────

    def _build_stmt(self, params: EventSearchParams):
        stmt = select(Event).where(Event.is_deleted == False)  # noqa: E712
        if params.company_id:
            stmt = stmt.where(Event.company_id == params.company_id)
        if params.event_type:
            stmt = stmt.where(Event.event_type == params.event_type)
        if params.importance:
            stmt = stmt.where(Event.importance == params.importance)
        if params.source:
            stmt = stmt.where(Event.source == params.source)
        if params.is_processed is not None:
            stmt = stmt.where(Event.is_processed == params.is_processed)
        if params.occurred_after:
            stmt = stmt.where(Event.occurred_at >= params.occurred_after)
        if params.occurred_before:
            stmt = stmt.where(Event.occurred_at <= params.occurred_before)
        if params.q:
            search_term = f"%{params.q.strip()}%"
            stmt = stmt.where(
                or_(Event.title.ilike(search_term), Event.summary.ilike(search_term))
            )
        return stmt

    async def search(
        self,
        params: EventSearchParams,
        offset: int = 0,
        limit: int = 20,
    ) -> list[Event]:
        stmt = self._build_stmt(params)
        stmt = stmt.order_by(Event.occurred_at.desc()).offset(offset).limit(min(limit, 100))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_search(self, params: EventSearchParams) -> int:
        stmt = select(func.count()).select_from(self._build_stmt(params).subquery())
        result = await self.session.execute(stmt)
        return result.scalar_one()

    # ── Events d'une entreprise ────────────────────────────────────────────────

    async def get_for_company(
        self,
        company_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Event]:
        result = await self.session.execute(
            select(Event)
            .where(Event.company_id == company_id, Event.is_deleted == False)  # noqa: E712
            .order_by(Event.occurred_at.desc())
            .offset(offset)
            .limit(min(limit, 100))
        )
        return list(result.scalars().all())

    async def count_for_company(self, company_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Event).where(
                Event.company_id == company_id,
                Event.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one()

    # ── Pour l'Opportunity Engine ──────────────────────────────────────────────

    async def get_unprocessed(self, limit: int = 100) -> list[Event]:
        """Récupère les events non encore traités par l'Opportunity Engine."""
        result = await self.session.execute(
            select(Event)
            .where(Event.is_processed == False, Event.is_deleted == False)  # noqa: E712
            .order_by(Event.occurred_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_processed_bulk(
        self, event_ids: list[uuid.UUID], version: int
    ) -> int:
        """Marque un batch d'events comme traités — appelé par l'Opportunity Engine."""
        result = await self.session.execute(
            update(Event)
            .where(Event.id.in_(event_ids))
            .values(is_processed=True, processing_version=version)
        )
        await self.session.flush()
        return result.rowcount

    async def get_stats_for_company(self, company_id: uuid.UUID) -> dict:
        """Agrégats pour EventStatsResponse — une seule requête."""
        events = await self.get_for_company(company_id, limit=1000)
        if not events:
            return {
                "total": 0,
                "unprocessed": 0,
                "by_type": {},
                "by_importance": {},
                "latest": None,
            }
        by_type: dict[str, int] = {}
        by_importance: dict[str, int] = {}
        unprocessed = 0
        for e in events:
            by_type[e.event_type] = by_type.get(e.event_type, 0) + 1
            by_importance[e.importance] = by_importance.get(e.importance, 0) + 1
            if not e.is_processed:
                unprocessed += 1
        return {
            "total": len(events),
            "unprocessed": unprocessed,
            "by_type": by_type,
            "by_importance": by_importance,
            "latest": events[0].occurred_at if events else None,
        }

    async def source_id_exists(self, source: str, source_id: str) -> bool:
        """Vérifie si un event avec ce source_id existe déjà."""
        return await self.get_by_source_id(source, source_id) is not None
