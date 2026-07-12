"""
Atlas - Opportunity Score Service
====================================
Fait le pont entre les modèles SQLAlchemy et le moteur pur OpportunityEngine.

Responsabilités :
1. Rassembler les signaux d'une entreprise (events, thèmes, profil, découvertes)
   et les traduire en dataclasses attendues par le moteur.
2. Appeler OpportunityEngine.compute() — aucune logique de scoring ici.
3. Persister le résultat via OpportunityScoreRepository.
4. Répercuter le score sur Company.atlas_score (déjà prévu par le Module 02).

Ce découpage garantit que le jour où le calcul migrera vers un modèle de
Machine Learning, seul OpportunityEngine change — ce service, les endpoints
et les schémas restent identiques.
"""

import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.engines.opportunity import (
    CompanySignal,
    DiscoverySignal,
    EventSignal,
    OpportunityEngine,
    OpportunityResult,
    ThemeSignal,
)
from app.models.company import Company
from app.models.opportunity import OpportunityScore
from app.repositories.company import CompanyRepository
from app.repositories.discovery import DiscoverySourceRepository
from app.repositories.event import EventRepository
from app.repositories.opportunity import OpportunityScoreRepository
from app.repositories.theme import ThemeRepository
from app.schemas.company import PaginatedResponse
from app.schemas.opportunity import (
    OpportunityListItem,
    OpportunityScoreResponse,
    OpportunitySearchParams,
    ScoreComponentSchema,
)
from app.services.company import CompanyService
from app.services.event import EventService

logger = get_logger(__name__)


class OpportunityScoreService:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = OpportunityScoreRepository(session)
        self.company_repo = CompanyRepository(session)
        self.event_repo = EventRepository(session)
        self.theme_repo = ThemeRepository(session)
        self.discovery_source_repo = DiscoverySourceRepository(session)
        self.engine = OpportunityEngine()

    # ── Lecture ──────────────────────────────────────────────────────────────

    async def get_or_compute(self, company_id: uuid.UUID) -> OpportunityScoreResponse:
        """
        Retourne le score existant, ou le calcule à la volée s'il n'existe pas
        encore — une entreprise n'a jamais de score "manquant" côté API.
        """
        existing = await self.repo.get_by_company(company_id)
        if existing:
            return self._to_response(existing)
        return await self.recompute(company_id)

    async def list_opportunities(
        self,
        params: OpportunitySearchParams,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse[OpportunityListItem]:
        offset = (page - 1) * page_size
        scores = await self.repo.list_ranked(
            offset=offset,
            limit=page_size,
            min_score=params.min_score,
            conviction=params.conviction,
            stage=params.stage,
            sector=params.sector,
            country=params.country,
            theme_id=params.theme_id,
            sort=params.sort,
        )
        total = await self.repo.count_ranked(
            min_score=params.min_score,
            conviction=params.conviction,
            stage=params.stage,
            sector=params.sector,
            country=params.country,
            theme_id=params.theme_id,
        )

        companies_by_id: dict[uuid.UUID, Company] = {}
        if scores:
            company_ids = [s.company_id for s in scores]
            result = await self.session.execute(
                select(Company).where(Company.id.in_(company_ids))
            )
            companies_by_id = {c.id: c for c in result.scalars().all()}

        items = []
        for s in scores:
            company = companies_by_id.get(s.company_id)
            items.append(
                OpportunityListItem(
                    company_id=s.company_id,
                    company_name=company.name if company else "Unknown",
                    company_slug=company.slug if company else "",
                    company_ticker=company.ticker if company else None,
                    company_sector=company.sector if company else None,
                    company_country=company.country if company else None,
                    company_logo_url=company.logo_url if company else None,
                    score=s.score,
                    conviction=s.conviction,
                    stage=s.stage,
                    calculated_at=s.calculated_at,
                )
            )

        return PaginatedResponse[OpportunityListItem](
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    # ── Calcul ───────────────────────────────────────────────────────────────

    async def recompute(self, company_id: uuid.UUID) -> OpportunityScoreResponse:
        """Force le recalcul complet du score d'une entreprise."""
        company = await self.company_repo.get_by_id(company_id)
        if not company:
            raise NotFoundError("Company", company_id)

        events = await self.event_repo.get_for_company(company_id, limit=1000)
        themes = await self.theme_repo.get_themes_for_company(company_id)
        discoveries = await self.discovery_source_repo.get_for_company(company_id)

        event_signals = [
            EventSignal(
                event_type=e.event_type,
                importance=e.importance,
                occurred_at=e.occurred_at,
                score_boost=EventService.get_score_boost(
                    e.event_type, e.importance, e.confidence_score
                ),
            )
            for e in events
            if not e.is_deleted
        ]
        theme_signals = [
            ThemeSignal(name=t.name, maturity_level=t.maturity_level) for t in themes
        ]
        discovery_signals = [
            DiscoverySignal(source=d.source, discovered_at=d.created_at) for d in discoveries
        ]
        company_signal = CompanySignal(
            has_description=bool(company.description),
            has_website=bool(company.website),
            has_sector=bool(company.sector),
            has_industry=bool(company.industry),
            has_employees=company.employees is not None,
            has_revenue=company.revenue_usd is not None,
            has_market_cap=company.market_cap_usd is not None,
            has_founded_year=company.founded_year is not None,
            has_logo=bool(company.logo_url),
            is_featured=company.is_featured,
            status=company.status,
        )

        result = self.engine.compute(
            events=event_signals,
            themes=theme_signals,
            company=company_signal,
            discoveries=discovery_signals,
            now=datetime.now(UTC),
        )

        record = await self.repo.upsert(
            company_id=company_id,
            score=result.score,
            conviction=result.conviction,
            stage=result.stage,
            stage_rationale=result.stage_rationale,
            components=self._serialize_components(result),
            positive_factors=result.positive_factors,
            negative_factors=result.negative_factors,
            scoring_version=self.engine.SCORING_VERSION,
            calculated_at=result.calculated_at,
        )

        # Répercute le score sur Company.atlas_score (champ prévu au Module 02)
        await CompanyService(self.session).update_atlas_score(company_id, result.score)

        # Marque les events consommés dans ce calcul comme traités
        processed_ids = [e.id for e in events if not e.is_deleted]
        if processed_ids:
            await self.event_repo.mark_processed_bulk(
                processed_ids, self.engine.SCORING_VERSION
            )

        logger.info(
            "Opportunity score computed",
            company_id=str(company_id),
            score=result.score,
            conviction=result.conviction.value,
            stage=result.stage.value,
            scoring_version=self.engine.SCORING_VERSION,
        )

        return self._to_response(record)

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _serialize_components(result: OpportunityResult) -> dict:
        return {
            name: {
                "name": c.name,
                "value": c.value,
                "weight": c.weight,
                "is_connected": c.is_connected,
                "positive_factors": c.positive_factors,
                "negative_factors": c.negative_factors,
            }
            for name, c in result.components.items()
        }

    def _to_response(self, record: OpportunityScore) -> OpportunityScoreResponse:
        components = {
            name: ScoreComponentSchema(**data) for name, data in record.components.items()
        }
        return OpportunityScoreResponse(
            id=record.id,
            company_id=record.company_id,
            score=record.score,
            conviction=record.conviction,
            stage=record.stage,
            stage_rationale=record.stage_rationale,
            components=components,
            positive_factors=record.positive_factors,
            negative_factors=record.negative_factors,
            scoring_version=record.scoring_version,
            calculated_at=record.calculated_at,
        )
