"""
Atlas - Snapshot Endpoints
==========================

GET /companies/{id}/prices        — Historique des prix capturés (public)
GET /companies/{id}/score-history — Historique des scores capturés (public)

Les listes sont renvoyées de la plus récente à la plus ancienne.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession
from app.repositories.snapshot import SnapshotRepository
from app.schemas.snapshot import PriceSnapshotResponse, ScoreSnapshotResponse

companies_router = APIRouter(prefix="/companies", tags=["Companies"])


async def get_snapshot_repo(db: DbSession) -> SnapshotRepository:
    return SnapshotRepository(db)


SnapshotRepoDep = Annotated[SnapshotRepository, Depends(get_snapshot_repo)]


@companies_router.get(
    "/{company_id}/prices",
    response_model=list[PriceSnapshotResponse],
    summary="Historique des prix capturés",
)
async def get_price_history(
    company_id: UUID,
    repo: SnapshotRepoDep,
    limit: int = Query(default=90, ge=1, le=365),
) -> list[PriceSnapshotResponse]:
    rows = await repo.price_history(company_id, limit=limit)
    return [PriceSnapshotResponse.model_validate(r) for r in rows]


@companies_router.get(
    "/{company_id}/score-history",
    response_model=list[ScoreSnapshotResponse],
    summary="Historique des scores capturés",
)
async def get_score_history(
    company_id: UUID,
    repo: SnapshotRepoDep,
    limit: int = Query(default=90, ge=1, le=365),
) -> list[ScoreSnapshotResponse]:
    rows = await repo.score_history(company_id, limit=limit)
    return [ScoreSnapshotResponse.model_validate(r) for r in rows]
