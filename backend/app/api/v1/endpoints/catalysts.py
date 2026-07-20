"""
Atlas - Catalyst Endpoints
==========================

GET    /catalysts                  — Catalyseurs à venir, tri chronologique (public)
POST   /catalysts                  — Ajouter un catalyseur manuel (public)
DELETE /catalysts/{id}             — Retirer un catalyseur (public)
GET    /companies/{id}/catalysts   — Catalyseurs d'une entreprise (public)

Public : cohérent avec le reste de l'app mono-utilisateur sans session.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import DbSession
from app.schemas.catalyst import CatalystCreate, CatalystResponse
from app.services.catalyst import CatalystService

router = APIRouter(prefix="/catalysts", tags=["Catalysts"])
companies_router = APIRouter(prefix="/companies", tags=["Companies"])


async def get_catalyst_service(db: DbSession) -> CatalystService:
    return CatalystService(db)


CatalystServiceDep = Annotated[CatalystService, Depends(get_catalyst_service)]


@router.get(
    "",
    response_model=list[CatalystResponse],
    summary="Catalyseurs à venir (tri chronologique)",
)
async def list_upcoming_catalysts(
    service: CatalystServiceDep,
    horizon_days: int = Query(default=365, ge=7, le=730),
) -> list[CatalystResponse]:
    return await service.list_upcoming(horizon_days)


@router.post(
    "",
    response_model=CatalystResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ajouter un catalyseur manuel",
)
async def create_catalyst(
    payload: CatalystCreate,
    service: CatalystServiceDep,
) -> CatalystResponse:
    return await service.create(payload)


@router.delete(
    "/{catalyst_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retirer un catalyseur",
)
async def delete_catalyst(
    catalyst_id: UUID,
    service: CatalystServiceDep,
) -> None:
    await service.delete(catalyst_id)


@companies_router.get(
    "/{company_id}/catalysts",
    response_model=list[CatalystResponse],
    summary="Catalyseurs d'une entreprise",
)
async def list_company_catalysts(
    company_id: UUID,
    service: CatalystServiceDep,
) -> list[CatalystResponse]:
    return await service.list_for_company(company_id)
