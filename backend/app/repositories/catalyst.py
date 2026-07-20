"""
Atlas - Catalyst Repository
===========================
"""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalyst import Catalyst


class CatalystRepository:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, catalyst_id: uuid.UUID) -> Catalyst | None:
        result = await self.session.execute(
            select(Catalyst).where(
                Catalyst.id == catalyst_id,
                Catalyst.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def list_upcoming(self, from_date: date, horizon_days: int) -> list[Catalyst]:
        """Catalyseurs à venir, du plus proche au plus lointain."""
        result = await self.session.execute(
            select(Catalyst)
            .where(
                Catalyst.is_deleted == False,  # noqa: E712
                Catalyst.status == "upcoming",
                Catalyst.expected_date >= from_date,
            )
            .order_by(Catalyst.expected_date.asc())
            .limit(500)
        )
        rows = list(result.scalars().all())
        limit_date = date.fromordinal(from_date.toordinal() + horizon_days)
        return [c for c in rows if c.expected_date <= limit_date]

    async def list_for_company(self, company_id: uuid.UUID) -> list[Catalyst]:
        result = await self.session.execute(
            select(Catalyst)
            .where(
                Catalyst.company_id == company_id,
                Catalyst.is_deleted == False,  # noqa: E712
            )
            .order_by(Catalyst.expected_date.asc())
        )
        return list(result.scalars().all())
