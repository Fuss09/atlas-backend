"""
Atlas - Theme Endpoints
=======================

GET    /themes                          — Liste des thèmes (public)
POST   /themes                          — Créer un thème (analyst+)
GET    /themes/categories               — Catégories disponibles (public)
GET    /themes/{id}                     — Détail par UUID (public)
GET    /themes/by-slug/{slug}           — Détail par slug (public)
PATCH  /themes/{id}                     — Mettre à jour (analyst+)
DELETE /themes/{id}                     — Soft delete (admin)
GET    /themes/{id}/companies           — Entreprises du thème (public)
POST   /themes/{id}/companies           — Associer une entreprise (analyst+)
DELETE /themes/{id}/companies/{cid}     — Dissocier une entreprise (analyst+)

GET    /companies/{id}/themes           — Thèmes d'une entreprise (public)
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser, DbSession, Pagination
from app.api.v1.endpoints.companies import require_admin, require_analyst
from app.schemas.company import CompanyListItem, PaginatedResponse
from app.schemas.theme import (
    CompanyThemeLink,
    ThemeCreate,
    ThemeListItem,
    ThemeResponse,
    ThemeUpdate,
)
from app.services.theme import ThemeService

router = APIRouter(prefix="/themes", tags=["Themes"])
companies_router = APIRouter(prefix="/companies", tags=["Companies"])


async def get_theme_service(db: DbSession) -> ThemeService:
    return ThemeService(db)


ThemeServiceDep = Annotated[ThemeService, Depends(get_theme_service)]


# ─── Lecture (publique) ───────────────────────────────────────────────────────

@router.get(
    "",
    response_model=list[ThemeListItem],
    summary="Lister les thèmes",
)
async def list_themes(
    theme_service: ThemeServiceDep,
    category: str | None = Query(default=None),
    maturity_level: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
) -> list[ThemeListItem]:
    return await theme_service.list_themes(
        include_inactive=include_inactive,
        category=category,
        maturity_level=maturity_level,
    )


@router.get(
    "/categories",
    response_model=list[str],
    summary="Catégories disponibles",
)
async def get_categories(theme_service: ThemeServiceDep) -> list[str]:
    return await theme_service.get_categories()


@router.get(
    "/by-slug/{slug}",
    response_model=ThemeResponse,
    summary="Détail par slug",
)
async def get_theme_by_slug(
    slug: str,
    theme_service: ThemeServiceDep,
) -> ThemeResponse:
    theme = await theme_service.get_by_slug(slug)
    return await theme_service.get_theme_detail(theme.id)


@router.get(
    "/{theme_id}",
    response_model=ThemeResponse,
    summary="Détail d'un thème",
)
async def get_theme(
    theme_id: UUID,
    theme_service: ThemeServiceDep,
) -> ThemeResponse:
    return await theme_service.get_theme_detail(theme_id)


@router.get(
    "/{theme_id}/companies",
    response_model=PaginatedResponse[CompanyListItem],
    summary="Entreprises d'un thème",
)
async def get_theme_companies(
    theme_id: UUID,
    theme_service: ThemeServiceDep,
    pagination: Pagination,
) -> PaginatedResponse[CompanyListItem]:
    return await theme_service.get_theme_companies(
        theme_id,
        page=pagination.page,
        page_size=pagination.page_size,
    )


# ─── Écriture (authentifiée) ──────────────────────────────────────────────────

@router.post(
    "",
    response_model=ThemeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un thème",
    dependencies=[Depends(require_analyst)],
)
async def create_theme(
    data: ThemeCreate,
    theme_service: ThemeServiceDep,
    current_user: CurrentUser,
) -> ThemeResponse:
    return await theme_service.create(data, created_by=current_user.id)


@router.patch(
    "/{theme_id}",
    response_model=ThemeResponse,
    summary="Mettre à jour un thème",
    dependencies=[Depends(require_analyst)],
)
async def update_theme(
    theme_id: UUID,
    data: ThemeUpdate,
    theme_service: ThemeServiceDep,
    current_user: CurrentUser,
) -> ThemeResponse:
    return await theme_service.update(theme_id, data, updated_by=current_user.id)


@router.delete(
    "/{theme_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un thème",
    dependencies=[Depends(require_admin)],
)
async def delete_theme(
    theme_id: UUID,
    theme_service: ThemeServiceDep,
    current_user: CurrentUser,
) -> None:
    await theme_service.delete(theme_id, deleted_by=current_user.id)


# ─── Association Company <-> Theme ────────────────────────────────────────────

@router.post(
    "/{theme_id}/companies",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Associer une entreprise à un thème",
    dependencies=[Depends(require_analyst)],
)
async def add_company_to_theme(
    theme_id: UUID,
    body: CompanyThemeLink,
    theme_service: ThemeServiceDep,
    current_user: CurrentUser,
) -> None:
    await theme_service.add_company(
        theme_id=theme_id,
        company_id=body.company_id,
        added_by=current_user.id,
    )


@router.delete(
    "/{theme_id}/companies/{company_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retirer une entreprise d'un thème",
    dependencies=[Depends(require_analyst)],
)
async def remove_company_from_theme(
    theme_id: UUID,
    company_id: UUID,
    theme_service: ThemeServiceDep,
    current_user: CurrentUser,
) -> None:
    await theme_service.remove_company(
        theme_id=theme_id,
        company_id=company_id,
        removed_by=current_user.id,
    )


# ─── Endpoint inversé : thèmes d'une entreprise ───────────────────────────────

@companies_router.get(
    "/{company_id}/themes",
    response_model=list[ThemeListItem],
    summary="Thèmes d'une entreprise",
    tags=["Companies"],
)
async def get_company_themes(
    company_id: UUID,
    theme_service: ThemeServiceDep,
) -> list[ThemeListItem]:
    return await theme_service.get_themes_for_company(company_id)
