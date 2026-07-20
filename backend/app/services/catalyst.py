"""
Atlas - Catalyst Service
========================
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.catalyst import Catalyst
from app.repositories.catalyst import CatalystRepository
from app.repositories.company import CompanyRepository
from app.schemas.catalyst import CatalystCreate, CatalystResponse

logger = get_logger(__name__)


class CatalystService:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = CatalystRepository(session)
        self.company_repo = CompanyRepository(session)

    async def list_upcoming(self, horizon_days: int) -> list[CatalystResponse]:
        today = datetime.now(UTC).date()
        rows = await self.repo.list_upcoming(today, horizon_days)
        return [CatalystResponse.model_validate(r) for r in rows]

    async def list_for_company(self, company_id: uuid.UUID) -> list[CatalystResponse]:
        rows = await self.repo.list_for_company(company_id)
        return [CatalystResponse.model_validate(r) for r in rows]

    async def create(self, payload: CatalystCreate) -> CatalystResponse:
        company = await self.company_repo.get_by_id(payload.company_id)
        if not company:
            raise NotFoundError("Company", payload.company_id)

        catalyst = Catalyst(
            company_id=payload.company_id,
            catalyst_type=payload.catalyst_type,
            title=payload.title,
            description=payload.description,
            expected_date=payload.expected_date,
            date_precision=payload.date_precision,
            source="manual",
            source_url=payload.source_url,
        )
        self.session.add(catalyst)
        await self.session.commit()
        await self.session.refresh(catalyst)
        logger.info(
            "Catalyst created",
            company_id=str(payload.company_id),
            expected_date=str(payload.expected_date),
        )
        return CatalystResponse.model_validate(catalyst)

    async def delete(self, catalyst_id: uuid.UUID) -> None:
        catalyst = await self.repo.get_by_id(catalyst_id)
        if not catalyst:
            raise NotFoundError("Catalyst", catalyst_id)
        catalyst.soft_delete()
        await self.session.commit()
        logger.info("Catalyst deleted", catalyst_id=str(catalyst_id))
