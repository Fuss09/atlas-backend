"""
Atlas - Event Endpoints
=======================

GET  /events                        — liste paginée (filtres)
POST /events                        — créer manuellement (analyst+)
GET  /events/types                  — types disponibles + boost
GET  /events/{id}                   — détail
PATCH /events/{id}                  — mettre à jour (analyst+)
DELETE /events/{id}                 — soft delete (admin)

GET  /companies/{id}/events         — events d'une entreprise
GET  /companies/{id}/events/stats   — statistiques agrégées
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser, DbSession, Pagination
from app.api.v1.endpoints.companies import require_admin, require_analyst
from app.models.event import EVENT_TYPE_SCORE_BOOST, IMPORTANCE_WEIGHTS, EventType, ImportanceLevel
from app.schemas.company import PaginatedResponse
from app.schemas.event import (
    EventCreate,
    EventListItem,
    EventResponse,
    EventSearchParams,
    EventStatsResponse,
    EventUpdate,
)
from app.services.event import EventService

router = APIRouter(prefix="/events", tags=["Events"])
companies_router = APIRouter(prefix="/companies", tags=["Companies"])


async def get_event_service(db: DbSession) -> EventService:
    return EventService(db)


EventServiceDep = Annotated[EventService, Depends(get_event_service)]


# ── Lecture ────────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=PaginatedResponse[EventListItem],
    summary="Lister les events",
)
async def list_events(
    event_service: EventServiceDep,
    pagination: Pagination,
    company_id: UUID | None = Query(default=None),
    event_type: EventType | None = Query(default=None),
    importance: ImportanceLevel | None = Query(default=None),
    source: str | None = Query(default=None, max_length=50),
    is_processed: bool | None = Query(default=None),
    occurred_after: str | None = Query(default=None, description="ISO 8601"),
    occurred_before: str | None = Query(default=None, description="ISO 8601"),
    q: str | None = Query(default=None, max_length=200, description="Recherche texte (titre, résumé)"),
) -> PaginatedResponse[EventListItem]:
    from datetime import datetime
    params = EventSearchParams(
        company_id=company_id,
        event_type=event_type,
        importance=importance,
        source=source,
        is_processed=is_processed,
        occurred_after=datetime.fromisoformat(occurred_after) if occurred_after else None,
        occurred_before=datetime.fromisoformat(occurred_before) if occurred_before else None,
        q=q,
    )
    return await event_service.list_events(params, page=pagination.page, page_size=pagination.page_size)


@router.get(
    "/types",
    summary="Types d'events disponibles",
    description="Retourne tous les types d'events avec leur boost de score associé.",
)
async def get_event_types() -> list[dict]:
    return [
        {
            "type": t.value,
            "score_boost": EVENT_TYPE_SCORE_BOOST.get(t, 1.0),
            "sentiment": "positive" if EVENT_TYPE_SCORE_BOOST.get(t, 0) > 0 else "negative",
        }
        for t in EventType
    ]


@router.get("/{event_id}", response_model=EventResponse, summary="Détail d'un event")
async def get_event(event_id: UUID, event_service: EventServiceDep) -> EventResponse:
    event = await event_service.get_by_id(event_id)
    return event_service._to_response(event)


# ── Écriture ───────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un event",
    dependencies=[Depends(require_analyst)],
)
async def create_event(
    data: EventCreate,
    event_service: EventServiceDep,
    current_user: CurrentUser,
) -> EventResponse:
    return await event_service.create(data, created_by=current_user.id)


@router.patch(
    "/{event_id}",
    response_model=EventResponse,
    summary="Mettre à jour un event",
    dependencies=[Depends(require_analyst)],
)
async def update_event(
    event_id: UUID,
    data: EventUpdate,
    event_service: EventServiceDep,
    current_user: CurrentUser,
) -> EventResponse:
    return await event_service.update(event_id, data, updated_by=current_user.id)


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un event",
    dependencies=[Depends(require_admin)],
)
async def delete_event(
    event_id: UUID,
    event_service: EventServiceDep,
    current_user: CurrentUser,
) -> None:
    await event_service.delete(event_id, deleted_by=current_user.id)


# ── Events d'une entreprise ────────────────────────────────────────────────────

@companies_router.get(
    "/{company_id}/events",
    response_model=PaginatedResponse[EventListItem],
    tags=["Companies"],
    summary="Events d'une entreprise",
)
async def get_company_events(
    company_id: UUID,
    event_service: EventServiceDep,
    pagination: Pagination,
) -> PaginatedResponse[EventListItem]:
    return await event_service.get_company_events(
        company_id, page=pagination.page, page_size=pagination.page_size
    )


@companies_router.get(
    "/{company_id}/events/stats",
    response_model=EventStatsResponse,
    tags=["Companies"],
    summary="Statistiques des events d'une entreprise",
)
async def get_company_event_stats(
    company_id: UUID,
    event_service: EventServiceDep,
) -> EventStatsResponse:
    return await event_service.get_stats(company_id)
