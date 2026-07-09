"""
Atlas - Company Repository
==========================
Couche d'accès aux données pour les entreprises.

Étend BaseRepository avec des requêtes spécifiques à Company :
- Recherche full-text PostgreSQL native (sans OpenSearch pour le MVP)
- Filtres combinables
- Comptage pour la pagination
- Récupération par ticker, ISIN, slug

Note sur la recherche :
Le Module 02 utilise la recherche PostgreSQL native (ILIKE + pg_trgm).
OpenSearch sera intégré dans le Module 07 (Search Engine) quand le volume
de données le justifiera. Cette approche évite une dépendance infrastructure
supplémentaire au stade MVP, conformément aux ADR en vigueur.
"""

import uuid
from typing import Any

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company, CompanyStatus, CompanyType
from app.repositories.base import BaseRepository
from app.schemas.company import CompanySearchParams, CompanySortOption


class CompanyRepository(BaseRepository[Company]):
    """
    Repository dédié aux entreprises.

    Toutes les requêtes excluent automatiquement les soft-deleted via BaseRepository.
    """

    model = Company

    # ─── Lookups par identifiant unique ───────────────────────────────────────

    async def get_by_slug(self, slug: str) -> Company | None:
        """Récupère une entreprise par son slug URL."""
        result = await self.session.execute(
            select(Company).where(
                Company.slug == slug,
                Company.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_by_ticker(self, ticker: str) -> Company | None:
        """Récupère une entreprise par son ticker (insensible à la casse)."""
        result = await self.session.execute(
            select(Company).where(
                func.upper(Company.ticker) == ticker.upper(),
                Company.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_by_isin(self, isin: str) -> Company | None:
        """Récupère une entreprise par son ISIN."""
        result = await self.session.execute(
            select(Company).where(
                Company.isin == isin.upper(),
                Company.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    # ─── Vérifications d'unicité ──────────────────────────────────────────────

    async def slug_exists(self, slug: str, exclude_id: uuid.UUID | None = None) -> bool:
        """Vérifie si un slug est déjà utilisé."""
        stmt = select(Company.id).where(
            Company.slug == slug,
            Company.is_deleted == False,  # noqa: E712
        )
        if exclude_id:
            stmt = stmt.where(Company.id != exclude_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def ticker_exists(self, ticker: str, exclude_id: uuid.UUID | None = None) -> bool:
        """Vérifie si un ticker est déjà utilisé."""
        stmt = select(Company.id).where(
            func.upper(Company.ticker) == ticker.upper(),
            Company.is_deleted == False,  # noqa: E712
        )
        if exclude_id:
            stmt = stmt.where(Company.id != exclude_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def isin_exists(self, isin: str, exclude_id: uuid.UUID | None = None) -> bool:
        """Vérifie si un ISIN est déjà utilisé."""
        stmt = select(Company.id).where(
            Company.isin == isin.upper(),
            Company.is_deleted == False,  # noqa: E712
        )
        if exclude_id:
            stmt = stmt.where(Company.id != exclude_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    # ─── Recherche et filtrage ────────────────────────────────────────────────

    def _build_search_stmt(self, params: CompanySearchParams):
        """
        Construit la requête SQLAlchemy selon les paramètres de recherche.
        Méthode interne partagée entre search() et count_search().
        """
        stmt = select(Company).where(Company.is_deleted == False)  # noqa: E712

        # Recherche textuelle : nom, ticker, description courte
        # Utilise ILIKE pour la recherche insensible à la casse
        # pg_trgm est activé en DB pour accélérer ces requêtes
        if params.q:
            search_term = f"%{params.q.strip()}%"
            stmt = stmt.where(
                or_(
                    Company.name.ilike(search_term),
                    Company.ticker.ilike(search_term),
                    Company.description_short.ilike(search_term),
                    cast(Company.isin, String).ilike(search_term),
                )
            )

        # Filtres exacts
        if params.sector:
            stmt = stmt.where(Company.sector.ilike(f"%{params.sector}%"))
        if params.industry:
            stmt = stmt.where(Company.industry.ilike(f"%{params.industry}%"))
        if params.country:
            stmt = stmt.where(Company.country == params.country.upper())
        if params.company_type:
            stmt = stmt.where(Company.company_type == params.company_type)
        if params.status is not None:
            stmt = stmt.where(Company.status == params.status)
        if params.exchange:
            stmt = stmt.where(Company.exchange.ilike(f"%{params.exchange}%"))
        if params.is_featured is not None:
            stmt = stmt.where(Company.is_featured == params.is_featured)

        # Filtres de range
        if params.min_market_cap is not None:
            stmt = stmt.where(Company.market_cap_usd >= params.min_market_cap)
        if params.max_market_cap is not None:
            stmt = stmt.where(Company.market_cap_usd <= params.max_market_cap)
        if params.min_atlas_score is not None:
            stmt = stmt.where(Company.atlas_score >= params.min_atlas_score)

        # Filtre par tags (JSONB contains)
        if params.tags:
            for tag in params.tags:
                stmt = stmt.where(Company.tags.contains([tag]))

        return stmt

    async def search(
        self,
        params: CompanySearchParams,
        offset: int = 0,
        limit: int = 20,
    ) -> list[Company]:
        """
        Recherche des entreprises avec filtres combinables et pagination.

        Tri : piloté par params.sort. RELEVANCE (défaut) reproduit le tri
        historique — featured > score > capitalisation > nom — pensé pour
        ce qu'un investisseur veut voir en premier. Les autres options
        permettent un tri explicite pour les vues type tableau/classement.
        """
        limit = min(limit, 100)
        stmt = self._build_search_stmt(params)
        stmt = stmt.order_by(*self._sort_clauses(params.sort))
        stmt = stmt.offset(offset).limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def _sort_clauses(sort: CompanySortOption) -> tuple:
        """Traduit une option de tri publique en clauses ORDER BY SQLAlchemy."""
        if sort == CompanySortOption.NAME_ASC:
            return (Company.name.asc(),)
        if sort == CompanySortOption.NAME_DESC:
            return (Company.name.desc(),)
        if sort == CompanySortOption.MARKET_CAP_DESC:
            return (Company.market_cap_usd.desc().nulls_last(), Company.name.asc())
        if sort == CompanySortOption.MARKET_CAP_ASC:
            return (Company.market_cap_usd.asc().nulls_last(), Company.name.asc())
        if sort == CompanySortOption.SCORE_DESC:
            return (Company.atlas_score.desc().nulls_last(), Company.name.asc())
        if sort == CompanySortOption.SCORE_ASC:
            return (Company.atlas_score.asc().nulls_last(), Company.name.asc())
        if sort == CompanySortOption.FOUNDED_DESC:
            return (Company.founded_year.desc().nulls_last(), Company.name.asc())
        if sort == CompanySortOption.RECENTLY_UPDATED:
            return (Company.updated_at.desc(),)
        # RELEVANCE (défaut)
        return (
            Company.is_featured.desc(),
            Company.atlas_score.desc().nulls_last(),
            Company.market_cap_usd.desc().nulls_last(),
            Company.name.asc(),
        )

    async def count_search(self, params: CompanySearchParams) -> int:
        """Compte le nombre total de résultats pour la pagination."""
        stmt = self._build_search_stmt(params)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        result = await self.session.execute(count_stmt)
        return result.scalar_one()

    # ─── Requêtes métier spécifiques ─────────────────────────────────────────

    async def get_featured(self, limit: int = 10) -> list[Company]:
        """Retourne les entreprises mises en avant, triées par score."""
        result = await self.session.execute(
            select(Company)
            .where(
                Company.is_featured == True,  # noqa: E712
                Company.is_deleted == False,  # noqa: E712
                Company.status == CompanyStatus.ACTIVE,
            )
            .order_by(
                Company.atlas_score.desc().nulls_last(),
                Company.market_cap_usd.desc().nulls_last(),
            )
            .limit(min(limit, 50))
        )
        return list(result.scalars().all())

    async def get_by_sector(self, sector: str, limit: int = 20) -> list[Company]:
        """Retourne les entreprises d'un secteur donné."""
        result = await self.session.execute(
            select(Company)
            .where(
                Company.sector.ilike(f"%{sector}%"),
                Company.is_deleted == False,  # noqa: E712
                Company.status == CompanyStatus.ACTIVE,
            )
            .order_by(Company.market_cap_usd.desc().nulls_last())
            .limit(min(limit, 100))
        )
        return list(result.scalars().all())

    async def get_distinct_sectors(self) -> list[str]:
        """Retourne la liste des secteurs distincts présents dans la DB."""
        result = await self.session.execute(
            select(Company.sector)
            .where(
                Company.sector.is_not(None),
                Company.is_deleted == False,  # noqa: E712
            )
            .distinct()
            .order_by(Company.sector)
        )
        return [row[0] for row in result.all() if row[0]]

    async def get_distinct_countries(self) -> list[str]:
        """Retourne la liste des codes pays distincts."""
        result = await self.session.execute(
            select(Company.country)
            .where(Company.is_deleted == False)  # noqa: E712
            .distinct()
            .order_by(Company.country)
        )
        return [row[0] for row in result.all()]

    async def generate_unique_slug(self, base_slug: str) -> str:
        """
        Génère un slug unique en ajoutant un suffixe numérique si nécessaire.
        Ex: "nvidia-corporation" → "nvidia-corporation-2" si le premier existe.
        """
        slug = base_slug
        counter = 2
        while await self.slug_exists(slug):
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug
