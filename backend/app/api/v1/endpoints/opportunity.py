"""
Atlas - Opportunity Endpoints
===============================

GET  /companies/{id}/opportunity            — score actuel (calculé à la volée si absent)
POST /companies/{id}/opportunity/recompute  — force le recalcul (analyst+)
GET  /opportunities                         — entreprises triées par score décroissant
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, DbSession, Pagination
from app.api.v1.endpoints.companies import require_analyst
from app.engines.opportunity import ConvictionLevel, OpportunityStage
from app.schemas.company import PaginatedResponse
from app.schemas.opportunity import (
    OpportunityListItem,
    OpportunityScoreResponse,
    OpportunitySearchParams,
    OpportunitySortOption,
)
from app.services.opportunity import OpportunityScoreService

router = APIRouter(prefix="/opportunities", tags=["Opportunity Engine"])
companies_router = APIRouter(prefix="/companies", tags=["Companies"])


async def get_opportunity_service(db: DbSession) -> OpportunityScoreService:
    return OpportunityScoreService(db)


OpportunityServiceDep = Annotated[OpportunityScoreService, Depends(get_opportunity_service)]


# ── Score d'une entreprise ──────────────────────────────────────────────────────

@companies_router.get(
    "/{company_id}/opportunity",
    response_model=OpportunityScoreResponse,
    summary="Score d'opportunité d'une entreprise",
    description=(
        "Retourne le score d'opportunité de l'entreprise, entièrement explicable "
        "(détail par composant, facteurs positifs et négatifs). "
        "Si aucun score n'a encore été calculé, il est généré à la volée."
    ),
)
async def get_company_opportunity(
    company_id: UUID,
    opportunity_service: OpportunityServiceDep,
) -> OpportunityScoreResponse:
    return await opportunity_service.get_or_compute(company_id)


@companies_router.post(
    "/{company_id}/opportunity/recompute",
    response_model=OpportunityScoreResponse,
    summary="Forcer le recalcul du score",
    description="Recalcule le score depuis zéro à partir des signaux actuels de l'entreprise.",
    dependencies=[Depends(require_analyst)],
)
async def recompute_company_opportunity(
    company_id: UUID,
    opportunity_service: OpportunityServiceDep,
    current_user: CurrentUser,
) -> OpportunityScoreResponse:
    return await opportunity_service.recompute(company_id)


# ── Classement global ────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=PaginatedResponse[OpportunityListItem],
    summary="Entreprises classées par score d'opportunité",
)
async def list_opportunities(
    opportunity_service: OpportunityServiceDep,
    pagination: Pagination,
    min_score: int | None = Query(default=None, ge=0, le=100),
    conviction: ConvictionLevel | None = Query(default=None),
    stage: OpportunityStage | None = Query(default=None),
    sector: str | None = Query(default=None, max_length=100),
    country: str | None = Query(default=None, max_length=2, description="Code ISO 3166-1 alpha-2"),
    theme_id: UUID | None = Query(default=None),
    sort: str | None = Query(
        default=None,
        description="score_desc (default), score_asc, name_asc, recently_calculated",
    ),
) -> PaginatedResponse[OpportunityListItem]:
    sort_enum = OpportunitySortOption.SCORE_DESC
    if sort:
        try:
            sort_enum = OpportunitySortOption(sort)
        except ValueError:
            pass

    params = OpportunitySearchParams(
        min_score=min_score,
        conviction=conviction,
        stage=stage,
        sector=sector,
        country=country,
        theme_id=theme_id,
        sort=sort_enum,
    )
    return await opportunity_service.list_opportunities(
        params, page=pagination.page, page_size=pagination.page_size
    )
