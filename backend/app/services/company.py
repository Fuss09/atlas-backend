"""
Atlas - Company Service
=======================
Couche de logique métier pour les entreprises.

Responsabilités :
- Orchestrer les opérations sur les entreprises
- Valider les règles métier (unicité ticker/ISIN, slug disponible)
- Loguer les opérations importantes
- Préparer les données pour le repository

Le service ne connaît pas FastAPI.
Il ne manipule que des modèles, des schémas, et des exceptions Atlas.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AlreadyExistsError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.company import Company
from app.repositories.company import CompanyRepository
from app.schemas.company import (
    CompanyCreate,
    CompanyListItem,
    CompanyResponse,
    CompanySearchParams,
    CompanyUpdate,
    PaginatedResponse,
    _generate_slug,
)

logger = get_logger(__name__)


class CompanyService:
    """
    Service de gestion des entreprises.

    Toutes les opérations d'écriture sont loggées avec l'identifiant
    de l'utilisateur initiateur (pour l'audit trail).
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = CompanyRepository(session)

    # ─── Lecture ──────────────────────────────────────────────────────────────

    async def get_by_id(self, company_id: uuid.UUID) -> Company:
        """
        Récupère une entreprise par son ID.

        Raises:
            NotFoundError: Si l'entreprise n'existe pas.
        """
        company = await self.repo.get_by_id(company_id)
        if not company:
            raise NotFoundError("Company", company_id)
        return company

    async def get_by_slug(self, slug: str) -> Company:
        """
        Récupère une entreprise par son slug.
        Utilisé pour les URLs propres : /companies/nvidia-corporation

        Raises:
            NotFoundError: Si l'entreprise n'existe pas.
        """
        company = await self.repo.get_by_slug(slug)
        if not company:
            raise NotFoundError("Company", slug)
        return company

    async def get_by_ticker(self, ticker: str) -> Company:
        """
        Récupère une entreprise par son ticker.

        Raises:
            NotFoundError: Si l'entreprise n'existe pas.
        """
        company = await self.repo.get_by_ticker(ticker)
        if not company:
            raise NotFoundError("Company", f"ticker:{ticker.upper()}")
        return company

    async def list_companies(
        self,
        params: CompanySearchParams,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse[CompanyListItem]:
        """
        Retourne une liste paginée d'entreprises avec filtres.

        Le total est calculé en une requête COUNT séparée pour permettre
        l'affichage du nombre total de pages côté frontend.
        """
        offset = (page - 1) * page_size

        # Exécution en parallèle pour minimiser la latence
        import asyncio
        companies, total = await asyncio.gather(
            self.repo.search(params, offset=offset, limit=page_size),
            self.repo.count_search(params),
        )

        items = [CompanyListItem.model_validate(c) for c in companies]

        return PaginatedResponse[CompanyListItem](
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_featured(self, limit: int = 10) -> list[CompanyListItem]:
        """Retourne les entreprises mises en avant."""
        companies = await self.repo.get_featured(limit=limit)
        return [CompanyListItem.model_validate(c) for c in companies]

    async def get_sectors(self) -> list[str]:
        """Retourne la liste des secteurs disponibles (pour les filtres UI)."""
        return await self.repo.get_distinct_sectors()

    async def get_countries(self) -> list[str]:
        """Retourne la liste des pays disponibles (pour les filtres UI)."""
        return await self.repo.get_distinct_countries()

    # ─── Écriture ─────────────────────────────────────────────────────────────

    async def create(
        self,
        data: CompanyCreate,
        created_by: uuid.UUID | None = None,
    ) -> Company:
        """
        Crée une nouvelle entreprise.

        Validations métier :
        - Le ticker doit être unique (si fourni)
        - L'ISIN doit être unique (si fourni)
        - Le slug est généré et rendu unique automatiquement

        Args:
            data: Données validées de création.
            created_by: ID de l'utilisateur créateur (pour les logs).

        Returns:
            L'entreprise créée.

        Raises:
            AlreadyExistsError: Si ticker ou ISIN sont déjà utilisés.
        """
        # Unicité du ticker
        if data.ticker and await self.repo.ticker_exists(data.ticker):
            raise AlreadyExistsError("Company", "ticker", data.ticker)

        # Unicité de l'ISIN
        if data.isin and await self.repo.isin_exists(data.isin):
            raise AlreadyExistsError("Company", "isin", data.isin)

        # Unicité du slug (avec suffixe numérique si nécessaire)
        base_slug = data.slug or _generate_slug(data.name)
        unique_slug = await self.repo.generate_unique_slug(base_slug)

        # Extraction des données en dict pour le repository
        company_data = data.model_dump(exclude={"slug"})
        company_data["slug"] = unique_slug

        company = await self.repo.create(**company_data)

        logger.info(
            "Company created",
            company_id=str(company.id),
            name=company.name,
            ticker=company.ticker,
            created_by=str(created_by) if created_by else "system",
        )

        return company

    async def update(
        self,
        company_id: uuid.UUID,
        data: CompanyUpdate,
        updated_by: uuid.UUID | None = None,
    ) -> Company:
        """
        Met à jour une entreprise existante.

        Seuls les champs explicitement fournis (non-None) sont mis à jour.
        Les champs absents du payload ne sont pas modifiés.

        Raises:
            NotFoundError: Si l'entreprise n'existe pas.
            AlreadyExistsError: Si le nouveau ticker/ISIN est déjà utilisé.
        """
        # Vérifier que l'entreprise existe
        company = await self.get_by_id(company_id)

        # Unicité du ticker si changé
        if data.ticker and data.ticker != company.ticker:
            if await self.repo.ticker_exists(data.ticker, exclude_id=company_id):
                raise AlreadyExistsError("Company", "ticker", data.ticker)

        # Unicité de l'ISIN si changé
        if data.isin and data.isin != company.isin:
            if await self.repo.isin_exists(data.isin, exclude_id=company_id):
                raise AlreadyExistsError("Company", "isin", data.isin)

        # Mise à jour
        updates = data.model_dump(exclude_none=True)

        if not updates:
            return company  # Rien à mettre à jour

        updated = await self.repo.update(company_id, **updates)
        if not updated:
            raise NotFoundError("Company", company_id)

        logger.info(
            "Company updated",
            company_id=str(company_id),
            fields=list(updates.keys()),
            updated_by=str(updated_by) if updated_by else "system",
        )

        return updated

    async def delete(
        self,
        company_id: uuid.UUID,
        deleted_by: uuid.UUID | None = None,
    ) -> None:
        """
        Soft delete d'une entreprise.
        L'entreprise reste en base pour l'historique et le ML.

        Raises:
            NotFoundError: Si l'entreprise n'existe pas.
        """
        success = await self.repo.soft_delete(company_id)
        if not success:
            raise NotFoundError("Company", company_id)

        logger.info(
            "Company soft-deleted",
            company_id=str(company_id),
            deleted_by=str(deleted_by) if deleted_by else "system",
        )

    async def set_featured(
        self,
        company_id: uuid.UUID,
        featured: bool,
        updated_by: uuid.UUID | None = None,
    ) -> Company:
        """
        Active ou désactive la mise en avant d'une entreprise.
        Endpoint dédié pour éviter des updates accidentels via PATCH.
        """
        company = await self.get_by_id(company_id)
        updated = await self.repo.update(company_id, is_featured=featured)
        if not updated:
            raise NotFoundError("Company", company_id)

        logger.info(
            "Company featured status changed",
            company_id=str(company_id),
            is_featured=featured,
            updated_by=str(updated_by) if updated_by else "system",
        )

        return updated

    async def update_atlas_score(
        self,
        company_id: uuid.UUID,
        score: int,
    ) -> Company:
        """
        Met à jour le score Atlas d'une entreprise.
        Appelé par l'Opportunity Engine (Module 05).

        Args:
            score: Valeur entre 0 et 100.
        """
        if not 0 <= score <= 100:
            raise ValidationError(
                "Atlas score must be between 0 and 100",
                details={"score": score},
            )

        updated = await self.repo.update(company_id, atlas_score=score)
        if not updated:
            raise NotFoundError("Company", company_id)

        logger.info(
            "Company atlas_score updated",
            company_id=str(company_id),
            score=score,
        )

        return updated
