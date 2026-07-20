"""
Atlas - Watchlist Endpoints
===========================

GET    /watchlist              — Entrées de la watchlist, avec entreprises (public)
GET    /watchlist/ids          — IDs des entreprises suivies, léger (public)
POST   /watchlist              — Ajouter une entreprise (public, idempotent)
DELETE /watchlist/{company_id} — Retirer une entreprise (public)

Public : l'app est mono-utilisateur sans session active, comme les lectures
companies/themes/events. Quand l'auth sera branchée (déploiement), ces
endpoints prendront CurrentUser — même bascule que le reste de l'app.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import DbSession
from app.schemas.watchlist import WatchlistAdd, WatchlistIdsResponse, WatchlistItemResponse
from app.services.watchlist import WatchlistService

router = APIRouter(prefix="/watchlist", tags=["Watchlist"])


async def get_watchlist_service(db: DbSession) -> WatchlistService:
    return WatchlistService(db)


WatchlistServiceDep = Annotated[WatchlistService, Depends(get_watchlist_service)]


@router.get(
    "",
    response_model=list[WatchlistItemResponse],
    summary="Lister la watchlist",
)
async def list_watchlist(service: WatchlistServiceDep) -> list[WatchlistItemResponse]:
    return await service.list_items()


@router.get(
    "/ids",
    response_model=WatchlistIdsResponse,
    summary="IDs des entreprises suivies (léger, pour l'état des boutons)",
)
async def list_watchlist_ids(service: WatchlistServiceDep) -> WatchlistIdsResponse:
    ids = await service.list_company_ids()
    return WatchlistIdsResponse(company_ids=ids)


@router.post(
    "",
    response_model=WatchlistItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ajouter une entreprise à la watchlist (idempotent)",
)
async def add_to_watchlist(
    payload: WatchlistAdd,
    service: WatchlistServiceDep,
) -> WatchlistItemResponse:
    return await service.add(payload.company_id, payload.notes)


@router.delete(
    "/{company_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retirer une entreprise de la watchlist",
)
async def remove_from_watchlist(
    company_id: UUID,
    service: WatchlistServiceDep,
) -> None:
    await service.remove(company_id)
