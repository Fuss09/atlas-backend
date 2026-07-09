"""
Atlas - Discovery Endpoints
============================

GET  /discovery/sources          — Sources disponibles et leur statut
GET  /discovery/jobs             — Historique des jobs
POST /discovery/jobs             — Déclencher un job (async, retourne immédiatement)
GET  /discovery/jobs/{id}        — Détail d'un job
POST /discovery/jobs/run-sync    — Exécuter un job en mode synchrone (tests)
GET  /companies/{id}/sources     — Historique de provenance d'une entreprise
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser, DbSession
from app.api.v1.endpoints.companies import require_admin, require_analyst
from app.collectors.registry import list_available_sources
from app.models.discovery import DiscoverySourceName
from app.schemas.discovery import (
    AvailableSource,
    DiscoveryJobResponse,
    DiscoveryJobSummary,
    TriggerJobRequest,
)
from app.services.discovery import DiscoveryService

router = APIRouter(prefix="/discovery", tags=["Discovery"])
companies_router = APIRouter(prefix="/companies", tags=["Companies"])


async def get_discovery_service(db: DbSession) -> DiscoveryService:
    return DiscoveryService(db)


DiscoveryServiceDep = Annotated[DiscoveryService, Depends(get_discovery_service)]


# ─── Sources ──────────────────────────────────────────────────────────────────

@router.get(
    "/sources",
    response_model=list[AvailableSource],
    summary="Sources de découverte disponibles",
    description="Liste toutes les sources avec leur statut d'implémentation.",
)
async def get_sources() -> list[AvailableSource]:
    return [AvailableSource(**s) for s in list_available_sources()]


# ─── Jobs ─────────────────────────────────────────────────────────────────────

@router.get(
    "/jobs",
    response_model=list[DiscoveryJobSummary],
    summary="Historique des discovery jobs",
    dependencies=[Depends(require_analyst)],
)
async def list_jobs(
    discovery_service: DiscoveryServiceDep,
    source: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[DiscoveryJobSummary]:
    jobs = await discovery_service.list_jobs(source=source, limit=limit)
    return [DiscoveryJobSummary.model_validate(j) for j in jobs]


@router.post(
    "/jobs",
    response_model=DiscoveryJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Déclencher un discovery job",
    description=(
        "Lance un collecteur en arrière-plan. "
        "Retourne immédiatement avec le job en statut PENDING. "
        "Suivre l'avancement via GET /discovery/jobs/{id}."
    ),
    dependencies=[Depends(require_analyst)],
)
async def trigger_job(
    body: TriggerJobRequest,
    discovery_service: DiscoveryServiceDep,
    current_user: CurrentUser,
) -> DiscoveryJobResponse:
    job = await discovery_service.trigger_job(
        source=body.source,
        params=body.params,
        triggered_by=current_user.id,
    )
    return DiscoveryJobResponse.model_validate(job)


@router.post(
    "/jobs/run-sync",
    response_model=DiscoveryJobResponse,
    summary="Exécuter un job en mode synchrone",
    description=(
        "Exécute un collecteur et attend la fin avant de répondre. "
        "Réservé aux tests et aux runs manuels. Requiert admin."
    ),
    dependencies=[Depends(require_admin)],
)
async def run_job_sync(
    body: TriggerJobRequest,
    discovery_service: DiscoveryServiceDep,
    current_user: CurrentUser,
) -> DiscoveryJobResponse:
    job = await discovery_service.run_job_sync(
        source=body.source,
        params=body.params,
        triggered_by=current_user.id,
    )
    return DiscoveryJobResponse.model_validate(job)


@router.get(
    "/jobs/{job_id}",
    response_model=DiscoveryJobResponse,
    summary="Détail d'un discovery job",
    dependencies=[Depends(require_analyst)],
)
async def get_job(
    job_id: UUID,
    discovery_service: DiscoveryServiceDep,
) -> DiscoveryJobResponse:
    job = await discovery_service.get_job(job_id)
    return DiscoveryJobResponse.model_validate(job)


# ─── Provenance des entreprises ───────────────────────────────────────────────

@companies_router.get(
    "/{company_id}/sources",
    response_model=list[dict],
    summary="Historique de provenance d'une entreprise",
    description="Retourne toutes les sources qui ont contribué à créer ou enrichir cette entreprise.",
    tags=["Companies"],
)
async def get_company_sources(
    company_id: UUID,
    discovery_service: DiscoveryServiceDep,
) -> list[dict]:
    sources = await discovery_service.source_repo.get_for_company(company_id)
    return [
        {
            "id": str(s.id),
            "source": s.source,
            "action": s.action,
            "external_id": s.external_id,
            "external_url": s.external_url,
            "created_at": s.created_at.isoformat(),
        }
        for s in sources
    ]
