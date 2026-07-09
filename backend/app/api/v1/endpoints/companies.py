"""
Atlas - Company Endpoints
=========================
API REST pour les entreprises.

Endpoints :
  GET    /companies              — Liste paginée avec recherche et filtres
  POST   /companies              — Créer une entreprise (admin)
  GET    /companies/featured     — Entreprises mises en avant
  GET    /companies/sectors      — Liste des secteurs disponibles
  GET    /companies/countries    — Liste des pays disponibles
  GET    /companies/{id}         — Détail par UUID
  GET    /companies/by-slug/{slug}   — Détail par slug
  GET    /companies/by-ticker/{ticker} — Détail par ticker
  PATCH  /companies/{id}         — Mettre à jour (admin)
  DELETE /companies/{id}         — Soft delete (admin)
  POST   /companies/{id}/feature — Activer/désactiver la mise en avant (admin)

Sécurité :
  - Les endpoints de lecture sont publics (pas d'authentification requise)
  - Les endpoints d'écriture nécessitent d'être authentifié + rôle analyst/admin
  - Le soft delete est irréversible via l'API (restauration uniquement via admin DB)

Design :
  - La recherche par slug et ticker utilisent des routes dédiées
    plutôt qu'un paramètre générique, pour des URLs propres et predictibles.
  - Le score Atlas n'est pas modifiable via ce CRUD — il est géré par l'Opportunity Engine.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser, DbSession, Pagination
from app.core.exceptions import PermissionDeniedError
from app.models.user import UserRole
from app.schemas.company import (
    CompanyCreate,
    CompanyListItem,
    CompanyResponse,
    CompanySearchParams,
    CompanySortOption,
    CompanyUpdate,
    PaginatedResponse,
)
from app.services.company import CompanyService

router = APIRouter(prefix="/companies", tags=["Companies"])


# ─── Dependency ───────────────────────────────────────────────────────────────

async def get_company_service(db: DbSession) -> CompanyService:
    """Fournit un CompanyService injecté avec la session DB."""
    return CompanyService(db)


CompanyServiceDep = Annotated[CompanyService, Depends(get_company_service)]


def require_analyst(current_user: CurrentUser) -> None:
    """
    Vérifie que l'utilisateur est au moins analyst.
    Injecté comme dépendance sur les endpoints d'écriture.
    """
    if current_user.role not in (UserRole.ANALYST, UserRole.ADMIN):
        raise PermissionDeniedError(
            "This action requires analyst or admin role",
            details={"required_role": "analyst", "current_role": current_user.role},
        )


def require_admin(current_user: CurrentUser) -> None:
    """Vérifie que l'utilisateur est admin."""
    if current_user.role != UserRole.ADMIN:
        raise PermissionDeniedError(
            "This action requires admin role",
            details={"required_role": "admin", "current_role": current_user.role},
        )


# ─── Endpoints de lecture (publics) ───────────────────────────────────────────

@router.get(
    "",
    response_model=PaginatedResponse[CompanyListItem],
    summary="Rechercher des entreprises",
    description=(
        "Retourne une liste paginée d'entreprises. "
        "Tous les filtres sont combinables. "
        "La recherche textuelle porte sur le nom, le ticker et la description."
    ),
)
async def list_companies(
    company_service: CompanyServiceDep,
    pagination: Pagination,
    # Paramètres de recherche passés comme query params individuels
    # (plus ergonomique que d'envoyer un body sur un GET)
    q: str | None = Query(default=None, max_length=200, description="Recherche textuelle"),
    sector: str | None = Query(default=None, max_length=100),
    industry: str | None = Query(default=None, max_length=150),
    country: str | None = Query(default=None, max_length=2, description="Code ISO 3166-1 alpha-2"),
    company_type: str | None = Query(default=None),
    exchange: str | None = Query(default=None, max_length=50),
    is_featured: bool | None = Query(default=None),
    min_market_cap: int | None = Query(default=None, ge=0),
    max_market_cap: int | None = Query(default=None, ge=0),
    min_atlas_score: int | None = Query(default=None, ge=0, le=100),
    sort: str | None = Query(
        default=None,
        description="relevance (default), name_asc, name_desc, market_cap_desc, "
        "market_cap_asc, score_desc, score_asc, founded_desc, recently_updated",
    ),
) -> PaginatedResponse[CompanyListItem]:
    from app.models.company import CompanyStatus, CompanyType as CT

    # Conversion du string en enum (FastAPI ne le fait pas automatiquement pour les Optional)
    ct_enum = None
    if company_type:
        try:
            ct_enum = CT(company_type)
        except ValueError:
            pass

    sort_enum = CompanySortOption.RELEVANCE
    if sort:
        try:
            sort_enum = CompanySortOption(sort)
        except ValueError:
            pass

    params = CompanySearchParams(
        q=q,
        sector=sector,
        industry=industry,
        country=country,
        company_type=ct_enum,
        exchange=exchange,
        is_featured=is_featured,
        min_market_cap=min_market_cap,
        max_market_cap=max_market_cap,
        min_atlas_score=min_atlas_score,
        status=CompanyStatus.ACTIVE,  # Toujours filtrer les inactives dans la liste publique
        sort=sort_enum,
    )

    return await company_service.list_companies(
        params=params,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/featured",
    response_model=list[CompanyListItem],
    summary="Entreprises mises en avant",
    description="Retourne les entreprises featured, triées par score Atlas.",
)
async def get_featured_companies(
    company_service: CompanyServiceDep,
    limit: int = Query(default=10, ge=1, le=50),
) -> list[CompanyListItem]:
    return await company_service.get_featured(limit=limit)


@router.get(
    "/sectors",
    response_model=list[str],
    summary="Secteurs disponibles",
    description="Liste des secteurs présents dans la base (pour alimenter les filtres UI).",
)
async def get_sectors(company_service: CompanyServiceDep) -> list[str]:
    return await company_service.get_sectors()


@router.get(
    "/countries",
    response_model=list[str],
    summary="Pays disponibles",
    description="Liste des codes pays présents dans la base.",
)
async def get_countries(company_service: CompanyServiceDep) -> list[str]:
    return await company_service.get_countries()


@router.get(
    "/by-ticker/{ticker}",
    response_model=CompanyResponse,
    summary="Rechercher par ticker",
    description="Récupère une entreprise par son symbole boursier (insensible à la casse).",
)
async def get_company_by_ticker(
    ticker: str,
    company_service: CompanyServiceDep,
) -> CompanyResponse:
    company = await company_service.get_by_ticker(ticker)
    return CompanyResponse.model_validate(company)


@router.get(
    "/by-slug/{slug}",
    response_model=CompanyResponse,
    summary="Rechercher par slug",
    description="Récupère une entreprise par son slug URL (ex: nvidia-corporation).",
)
async def get_company_by_slug(
    slug: str,
    company_service: CompanyServiceDep,
) -> CompanyResponse:
    company = await company_service.get_by_slug(slug)
    return CompanyResponse.model_validate(company)


@router.get(
    "/{company_id}",
    response_model=CompanyResponse,
    summary="Détail d'une entreprise",
    description="Retourne tous les champs d'une entreprise par son UUID.",
)
async def get_company(
    company_id: UUID,
    company_service: CompanyServiceDep,
) -> CompanyResponse:
    company = await company_service.get_by_id(company_id)
    return CompanyResponse.model_validate(company)


# ─── Endpoints d'écriture (authentifiés) ──────────────────────────────────────

@router.post(
    "",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une entreprise",
    description="Crée une nouvelle entreprise. Requiert le rôle analyst ou admin.",
    dependencies=[Depends(require_analyst)],
)
async def create_company(
    data: CompanyCreate,
    company_service: CompanyServiceDep,
    current_user: CurrentUser,
) -> CompanyResponse:
    company = await company_service.create(data, created_by=current_user.id)
    return CompanyResponse.model_validate(company)


@router.patch(
    "/{company_id}",
    response_model=CompanyResponse,
    summary="Mettre à jour une entreprise",
    description=(
        "Mise à jour partielle d'une entreprise. "
        "Seuls les champs fournis sont mis à jour. "
        "Requiert le rôle analyst ou admin."
    ),
    dependencies=[Depends(require_analyst)],
)
async def update_company(
    company_id: UUID,
    data: CompanyUpdate,
    company_service: CompanyServiceDep,
    current_user: CurrentUser,
) -> CompanyResponse:
    company = await company_service.update(company_id, data, updated_by=current_user.id)
    return CompanyResponse.model_validate(company)


@router.delete(
    "/{company_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer une entreprise",
    description=(
        "Soft delete d'une entreprise. "
        "L'entreprise est conservée en base pour l'historique. "
        "Requiert le rôle admin."
    ),
    dependencies=[Depends(require_admin)],
)
async def delete_company(
    company_id: UUID,
    company_service: CompanyServiceDep,
    current_user: CurrentUser,
) -> None:
    await company_service.delete(company_id, deleted_by=current_user.id)


@router.post(
    "/{company_id}/feature",
    response_model=CompanyResponse,
    summary="Activer/désactiver la mise en avant",
    description="Active ou désactive la mise en avant d'une entreprise dans le dashboard. Requiert admin.",
    dependencies=[Depends(require_admin)],
)
async def set_company_featured(
    company_id: UUID,
    featured: bool,
    company_service: CompanyServiceDep,
    current_user: CurrentUser,
) -> CompanyResponse:
    company = await company_service.set_featured(
        company_id, featured, updated_by=current_user.id
    )
    return CompanyResponse.model_validate(company)
