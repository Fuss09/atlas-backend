"""
Atlas - Theme Repository
========================
Accès aux données pour les thèmes et leur association avec les entreprises.
"""

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.theme import Theme, company_themes
from app.repositories.base import BaseRepository


class ThemeRepository(BaseRepository[Theme]):

    model = Theme

    # ─── Lookups ──────────────────────────────────────────────────────────────

    async def get_by_slug(self, slug: str) -> Theme | None:
        result = await self.session.execute(
            select(Theme).where(
                Theme.slug == slug,
                Theme.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Theme | None:
        result = await self.session.execute(
            select(Theme).where(
                func.lower(Theme.name) == name.lower(),
                Theme.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def slug_exists(self, slug: str, exclude_id: uuid.UUID | None = None) -> bool:
        stmt = select(Theme.id).where(
            Theme.slug == slug,
            Theme.is_deleted == False,  # noqa: E712
        )
        if exclude_id:
            stmt = stmt.where(Theme.id != exclude_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def name_exists(self, name: str, exclude_id: uuid.UUID | None = None) -> bool:
        stmt = select(Theme.id).where(
            func.lower(Theme.name) == name.lower(),
            Theme.is_deleted == False,  # noqa: E712
        )
        if exclude_id:
            stmt = stmt.where(Theme.id != exclude_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    # ─── Listes ───────────────────────────────────────────────────────────────

    async def get_all_active(
        self,
        category: str | None = None,
        maturity_level: str | None = None,
    ) -> list[Theme]:
        """Retourne tous les thèmes actifs, filtrables par catégorie et maturité."""
        stmt = select(Theme).where(
            Theme.is_deleted == False,  # noqa: E712
            Theme.is_active == True,  # noqa: E712
        )
        if category:
            stmt = stmt.where(Theme.category.ilike(f"%{category}%"))
        if maturity_level:
            stmt = stmt.where(Theme.maturity_level == maturity_level)
        stmt = stmt.order_by(Theme.category.asc().nulls_last(), Theme.name.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all(
        self,
        include_inactive: bool = False,
        category: str | None = None,
        maturity_level: str | None = None,
    ) -> list[Theme]:
        """Retourne tous les thèmes (actifs + inactifs si demandé). Usage admin."""
        stmt = select(Theme).where(Theme.is_deleted == False)  # noqa: E712
        if not include_inactive:
            stmt = stmt.where(Theme.is_active == True)  # noqa: E712
        if category:
            stmt = stmt.where(Theme.category.ilike(f"%{category}%"))
        if maturity_level:
            stmt = stmt.where(Theme.maturity_level == maturity_level)
        stmt = stmt.order_by(Theme.category.asc().nulls_last(), Theme.name.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_distinct_categories(self) -> list[str]:
        result = await self.session.execute(
            select(Theme.category)
            .where(
                Theme.category.is_not(None),
                Theme.is_deleted == False,  # noqa: E712
                Theme.is_active == True,  # noqa: E712
            )
            .distinct()
            .order_by(Theme.category)
        )
        return [row[0] for row in result.all() if row[0]]

    # ─── Comptages ────────────────────────────────────────────────────────────

    async def count_companies(self, theme_id: uuid.UUID) -> int:
        """Nombre d'entreprises associées à un thème."""
        result = await self.session.execute(
            select(func.count())
            .select_from(company_themes)
            .join(Company, Company.id == company_themes.c.company_id)
            .where(
                company_themes.c.theme_id == theme_id,
                Company.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one()

    async def count_companies_bulk(self, theme_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        """Compte les entreprises pour une liste de thèmes en une seule requête."""
        if not theme_ids:
            return {}
        result = await self.session.execute(
            select(
                company_themes.c.theme_id,
                func.count(company_themes.c.company_id).label("cnt"),
            )
            .join(Company, Company.id == company_themes.c.company_id)
            .where(
                company_themes.c.theme_id.in_(theme_ids),
                Company.is_deleted == False,  # noqa: E712
            )
            .group_by(company_themes.c.theme_id)
        )
        return {row.theme_id: row.cnt for row in result.all()}

    # ─── Entreprises d'un thème ───────────────────────────────────────────────

    async def get_companies(
        self,
        theme_id: uuid.UUID,
        offset: int = 0,
        limit: int = 20,
    ) -> list[Company]:
        """Retourne les entreprises d'un thème, triées par market_cap desc."""
        limit = min(limit, 100)
        result = await self.session.execute(
            select(Company)
            .join(company_themes, company_themes.c.company_id == Company.id)
            .where(
                company_themes.c.theme_id == theme_id,
                Company.is_deleted == False,  # noqa: E712
            )
            .order_by(
                Company.is_featured.desc(),
                Company.atlas_score.desc().nulls_last(),
                Company.market_cap_usd.desc().nulls_last(),
                Company.name.asc(),
            )
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_themes_for_company(self, company_id: uuid.UUID) -> list[Theme]:
        """Retourne les thèmes d'une entreprise."""
        result = await self.session.execute(
            select(Theme)
            .join(company_themes, company_themes.c.theme_id == Theme.id)
            .where(
                company_themes.c.company_id == company_id,
                Theme.is_deleted == False,  # noqa: E712
                Theme.is_active == True,  # noqa: E712
            )
            .order_by(Theme.name)
        )
        return list(result.scalars().all())

    # ─── Association / Dissociation ───────────────────────────────────────────

    async def association_exists(
        self, company_id: uuid.UUID, theme_id: uuid.UUID
    ) -> bool:
        result = await self.session.execute(
            select(func.count())
            .select_from(company_themes)
            .where(
                company_themes.c.company_id == company_id,
                company_themes.c.theme_id == theme_id,
            )
        )
        return result.scalar_one() > 0

    async def add_company(
        self,
        company_id: uuid.UUID,
        theme_id: uuid.UUID,
        added_by: uuid.UUID | None = None,
    ) -> None:
        """Associe une entreprise à un thème (INSERT OR IGNORE)."""
        if not await self.association_exists(company_id, theme_id):
            await self.session.execute(
                company_themes.insert().values(
                    company_id=company_id,
                    theme_id=theme_id,
                    added_by=added_by,
                )
            )
            await self.session.flush()

    async def remove_company(
        self,
        company_id: uuid.UUID,
        theme_id: uuid.UUID,
    ) -> bool:
        """Dissocie une entreprise d'un thème. Retourne True si l'association existait."""
        result = await self.session.execute(
            delete(company_themes).where(
                company_themes.c.company_id == company_id,
                company_themes.c.theme_id == theme_id,
            )
        )
        await self.session.flush()
        return result.rowcount > 0

    async def generate_unique_slug(self, base_slug: str) -> str:
        slug = base_slug
        counter = 2
        while await self.slug_exists(slug):
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug
