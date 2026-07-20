"""
Atlas - Snapshot Repository
===========================
Lecture de l'historique immuable prix/scores (le script de capture écrit
directement — ce repository ne sert que les endpoints de consultation).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.snapshot import PriceSnapshot, ScoreSnapshot


class SnapshotRepository:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def price_history(
        self, company_id: uuid.UUID, limit: int = 90
    ) -> list[PriceSnapshot]:
        result = await self.session.execute(
            select(PriceSnapshot)
            .where(PriceSnapshot.company_id == company_id)
            .order_by(PriceSnapshot.captured_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def score_history(
        self, company_id: uuid.UUID, limit: int = 90
    ) -> list[ScoreSnapshot]:
        result = await self.session.execute(
            select(ScoreSnapshot)
            .where(ScoreSnapshot.company_id == company_id)
            .order_by(ScoreSnapshot.captured_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
