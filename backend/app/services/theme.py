"""
Atlas - Theme Service
=====================
Logique métier pour les thèmes d'investissement.
"""

import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AlreadyExistsError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.theme import Theme
from app.repositories.company import CompanyRepository
from app.repositories.theme import ThemeRepository
from app.schemas.company import CompanyListItem, PaginatedResponse
from app.schemas.theme import (
    ThemeCreate,
    ThemeListItem,
    ThemeResponse,
    ThemeUpdate,
    ThemeWithCompanies,
    _generate_theme_slug,
)

logger = get_logger(__name__)


class ThemeService:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ThemeRepository(session)
        self.company_repo = CompanyRepository(session)

    # ─── Lecture ──────────────────────────────────────────────────────────────

    async def get_by_id(self, theme_id: uuid.UUID) -> Theme:
        theme = await self.repo.get_by_id(theme_id)
        if not theme:
            raise NotFoundError("Theme", theme_id)
        return theme

    async def get_by_slug(self, slug: str) -> Theme:
        theme = await self.repo.get_by_slug(slug)
        if not theme:
            raise NotFoundError("Theme", slug)
        return theme

    async def list_themes(
        self,
        include_inactive: bool = False,
        category: str | None = None,
        maturity_level: str | None = None,
    ) -> list[ThemeListItem]:
        """
        Liste tous les thèmes avec leur nombre d'entreprises.
        Le count est calculé en une seule requête GROUP BY.
        """
        themes = await self.repo.get_all(
            include_inactive=include_inactive,
            category=category,
            maturity_level=maturity_level,
        )
        if not themes:
            return []

        counts = await self.repo.count_companies_bulk([t.id for t in themes])

        items = []
        for t in themes:
            item = ThemeListItem.model_validate(t)
            item.companies_count = counts.get(t.id, 0)
            items.append(item)
        return items

    async def get_theme_detail(self, theme_id: uuid.UUID) -> ThemeResponse:
        """Retourne un thème avec son nombre d'entreprises."""
        theme = await self.get_by_id(theme_id)
        count = await self.repo.count_companies(theme_id)
        response = ThemeResponse.model_validate(theme)
        response.companies_count = count
        return response

    async def get_theme_companies(
        self,
        theme_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse[CompanyListItem]:
        """
        Retourne les entreprises d'un thème paginées.
        COUNT et résultats en parallèle.
        """
        await self.get_by_id(theme_id)  # 404 si inexistant
        offset = (page - 1) * page_size

        companies, total = await asyncio.gather(
            self.repo.get_companies(theme_id, offset=offset, limit=page_size),
            self.repo.count_companies(theme_id),
        )

        return PaginatedResponse[CompanyListItem](
            items=[CompanyListItem.model_validate(c) for c in companies],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_themes_for_company(self, company_id: uuid.UUID) -> list[ThemeListItem]:
        """Retourne les thèmes d'une entreprise."""
        company = await self.company_repo.get_by_id(company_id)
        if not company:
            raise NotFoundError("Company", company_id)
        themes = await self.repo.get_themes_for_company(company_id)
        counts = await self.repo.count_companies_bulk([t.id for t in themes])
        items = []
        for t in themes:
            item = ThemeListItem.model_validate(t)
            item.companies_count = counts.get(t.id, 0)
            items.append(item)
        return items

    async def get_categories(self) -> list[str]:
        return await self.repo.get_distinct_categories()

    # ─── Écriture ─────────────────────────────────────────────────────────────

    async def create(
        self,
        data: ThemeCreate,
        created_by: uuid.UUID | None = None,
    ) -> ThemeResponse:
        if await self.repo.name_exists(data.name):
            raise AlreadyExistsError("Theme", "name", data.name)

        base_slug = data.slug or _generate_theme_slug(data.name)
        unique_slug = await self.repo.generate_unique_slug(base_slug)

        theme_data = data.model_dump(exclude={"slug"})
        theme_data["slug"] = unique_slug

        theme = await self.repo.create(**theme_data)

        logger.info(
            "Theme created",
            theme_id=str(theme.id),
            name=theme.name,
            created_by=str(created_by) if created_by else "system",
        )

        response = ThemeResponse.model_validate(theme)
        response.companies_count = 0
        return response

    async def update(
        self,
        theme_id: uuid.UUID,
        data: ThemeUpdate,
        updated_by: uuid.UUID | None = None,
    ) -> ThemeResponse:
        theme = await self.get_by_id(theme_id)

        if data.name and data.name.lower() != theme.name.lower():
            if await self.repo.name_exists(data.name, exclude_id=theme_id):
                raise AlreadyExistsError("Theme", "name", data.name)

        updates = data.model_dump(exclude_none=True)
        if not updates:
            count = await self.repo.count_companies(theme_id)
            response = ThemeResponse.model_validate(theme)
            response.companies_count = count
            return response

        updated = await self.repo.update(theme_id, **updates)
        if not updated:
            raise NotFoundError("Theme", theme_id)

        logger.info(
            "Theme updated",
            theme_id=str(theme_id),
            fields=list(updates.keys()),
            updated_by=str(updated_by) if updated_by else "system",
        )

        count = await self.repo.count_companies(theme_id)
        response = ThemeResponse.model_validate(updated)
        response.companies_count = count
        return response

    async def delete(
        self,
        theme_id: uuid.UUID,
        deleted_by: uuid.UUID | None = None,
    ) -> None:
        success = await self.repo.soft_delete(theme_id)
        if not success:
            raise NotFoundError("Theme", theme_id)
        logger.info(
            "Theme soft-deleted",
            theme_id=str(theme_id),
            deleted_by=str(deleted_by) if deleted_by else "system",
        )

    # ─── Association Company <-> Theme ─────────────────────────────────────────

    async def add_company(
        self,
        theme_id: uuid.UUID,
        company_id: uuid.UUID,
        added_by: uuid.UUID | None = None,
    ) -> None:
        """
        Associe une entreprise à un thème.
        Idempotent : si l'association existe déjà, ne fait rien.
        """
        theme = await self.get_by_id(theme_id)
        if not theme.is_active:
            raise ValidationError(
                "Cannot add company to inactive theme",
                details={"theme_id": str(theme_id)},
            )

        company = await self.company_repo.get_by_id(company_id)
        if not company:
            raise NotFoundError("Company", company_id)

        await self.repo.add_company(company_id, theme_id, added_by=added_by)

        logger.info(
            "Company added to theme",
            theme_id=str(theme_id),
            company_id=str(company_id),
            added_by=str(added_by) if added_by else "system",
        )

    async def remove_company(
        self,
        theme_id: uuid.UUID,
        company_id: uuid.UUID,
        removed_by: uuid.UUID | None = None,
    ) -> None:
        """
        Dissocie une entreprise d'un thème.

        Raises:
            NotFoundError: Si le thème ou l'association n'existe pas.
        """
        await self.get_by_id(theme_id)

        removed = await self.repo.remove_company(company_id, theme_id)
        if not removed:
            raise NotFoundError(
                "CompanyTheme",
                f"company={company_id}, theme={theme_id}",
            )

        logger.info(
            "Company removed from theme",
            theme_id=str(theme_id),
            company_id=str(company_id),
            removed_by=str(removed_by) if removed_by else "system",
        )
