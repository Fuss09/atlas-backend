"""
Atlas - Opportunity Score Repository
======================================
"""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.opportunity import ConvictionLevel, OpportunityScore
from app.models.theme import company_themes
from app.repositories.base import BaseRepository
from app.schemas.opportunity import OpportunitySortOption


class OpportunityScoreRepository(BaseRepository[OpportunityScore]):

    model = OpportunityScore

    async def get_by_company(self, company_id: uuid.UUID) -> OpportunityScore | None:
        """Récupère le score actif d'une entreprise (il n'y en a qu'un seul)."""
        result = await self.session.execute(
            select(OpportunityScore).where(
                OpportunityScore.company_id == company_id,
                OpportunityScore.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        company_id: uuid.UUID,
        score: int,
        conviction: ConvictionLevel,
        stage: str,
        stage_rationale: str,
        components: dict,
        positive_factors: list[str],
        negative_factors: list[str],
        scoring_version: int,
        calculated_at: datetime,
    ) -> OpportunityScore:
        """
        Crée ou met à jour le score d'une entreprise.
        Une seule ligne active par entreprise — le recalcul écrase l'ancien score.
        """
        existing = await self.get_by_company(company_id)

        values = {
            "score": score,
            "conviction": conviction,
            "stage": stage,
            "stage_rationale": stage_rationale,
            "components": components,
            "positive_factors": positive_factors,
            "negative_factors": negative_factors,
            "scoring_version": scoring_version,
            "calculated_at": calculated_at,
        }

        if existing:
            for field, value in values.items():
                setattr(existing, field, value)
            await self.session.flush()
            await self.session.refresh(existing)
            return existing

        return await self.create(company_id=company_id, **values)

    # ── Classement pour GET /opportunities ──────────────────────────────────────

    def _build_ranking_stmt(
        self,
        min_score: int | None = None,
        conviction: ConvictionLevel | None = None,
        stage: str | None = None,
        sector: str | None = None,
        country: str | None = None,
        theme_id: uuid.UUID | None = None,
        needs_company_join: bool = False,
    ):
        stmt = select(OpportunityScore).where(OpportunityScore.is_deleted == False)  # noqa: E712
        if min_score is not None:
            stmt = stmt.where(OpportunityScore.score >= min_score)
        if conviction is not None:
            stmt = stmt.where(OpportunityScore.conviction == conviction)
        if stage is not None:
            stmt = stmt.where(OpportunityScore.stage == stage)

        # sector/country/name-sort nécessitent une jointure vers Company ;
        # theme_id nécessite en plus la table d'association company_themes.
        # On ne joint que si effectivement demandé, pour ne pas alourdir
        # la requête par défaut (cas le plus fréquent : aucun filtre).
        if sector is not None or country is not None or needs_company_join:
            stmt = stmt.join(Company, Company.id == OpportunityScore.company_id)
            if sector is not None:
                stmt = stmt.where(Company.sector == sector)
            if country is not None:
                stmt = stmt.where(Company.country == country.upper())

        if theme_id is not None:
            stmt = stmt.join(
                company_themes, company_themes.c.company_id == OpportunityScore.company_id
            ).where(company_themes.c.theme_id == theme_id)

        return stmt

    @staticmethod
    def _sort_clauses(sort: OpportunitySortOption):
        if sort == OpportunitySortOption.SCORE_ASC:
            return (OpportunityScore.score.asc(),)
        if sort == OpportunitySortOption.NAME_ASC:
            return (Company.name.asc(),)
        if sort == OpportunitySortOption.RECENTLY_CALCULATED:
            return (OpportunityScore.calculated_at.desc(),)
        # SCORE_DESC (défaut) — comportement historique préservé
        return (OpportunityScore.score.desc(),)

    async def list_ranked(
        self,
        offset: int = 0,
        limit: int = 20,
        min_score: int | None = None,
        conviction: ConvictionLevel | None = None,
        stage: str | None = None,
        sector: str | None = None,
        country: str | None = None,
        theme_id: uuid.UUID | None = None,
        sort: OpportunitySortOption = OpportunitySortOption.SCORE_DESC,
    ) -> list[OpportunityScore]:
        stmt = self._build_ranking_stmt(
            min_score, conviction, stage, sector, country, theme_id,
            needs_company_join=(sort == OpportunitySortOption.NAME_ASC),
        )
        stmt = (
            stmt.order_by(*self._sort_clauses(sort))
            .offset(offset)
            .limit(min(limit, 100))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_ranked(
        self,
        min_score: int | None = None,
        conviction: ConvictionLevel | None = None,
        stage: str | None = None,
        sector: str | None = None,
        country: str | None = None,
        theme_id: uuid.UUID | None = None,
    ) -> int:
        stmt = self._build_ranking_stmt(min_score, conviction, stage, sector, country, theme_id)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        result = await self.session.execute(count_stmt)
        return result.scalar_one()
