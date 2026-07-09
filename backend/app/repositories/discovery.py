"""
Atlas - Discovery Repository
=============================
Accès aux données pour les DiscoveryJob et DiscoverySource.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.discovery import DiscoveryJob, DiscoverySource, JobStatus


class DiscoveryJobRepository:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        source: str,
        triggered_by: uuid.UUID | None = None,
        params: dict | None = None,
    ) -> DiscoveryJob:
        job = DiscoveryJob(
            source=source,
            status=JobStatus.PENDING,
            triggered_by=triggered_by,
            params=params,
        )
        self.session.add(job)
        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def get_by_id(self, job_id: uuid.UUID) -> DiscoveryJob | None:
        result = await self.session.execute(
            select(DiscoveryJob).where(DiscoveryJob.id == job_id)
        )
        return result.scalar_one_or_none()

    async def list_recent(
        self,
        source: str | None = None,
        limit: int = 50,
    ) -> list[DiscoveryJob]:
        stmt = select(DiscoveryJob).order_by(DiscoveryJob.created_at.desc()).limit(limit)
        if source:
            stmt = stmt.where(DiscoveryJob.source == source)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def mark_running(self, job_id: uuid.UUID) -> None:
        await self.session.execute(
            update(DiscoveryJob)
            .where(DiscoveryJob.id == job_id)
            .values(status=JobStatus.RUNNING, started_at=datetime.now(UTC))
        )
        await self.session.flush()

    async def mark_finished(
        self,
        job_id: uuid.UUID,
        status: JobStatus,
        companies_found: int = 0,
        companies_created: int = 0,
        companies_updated: int = 0,
        companies_skipped: int = 0,
        errors: list | None = None,
        meta: dict | None = None,
    ) -> None:
        await self.session.execute(
            update(DiscoveryJob)
            .where(DiscoveryJob.id == job_id)
            .values(
                status=status,
                finished_at=datetime.now(UTC),
                companies_found=companies_found,
                companies_created=companies_created,
                companies_updated=companies_updated,
                companies_skipped=companies_skipped,
                errors=errors or [],
                meta=meta or {},
            )
        )
        await self.session.flush()


class DiscoverySourceRepository:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        company_id: uuid.UUID,
        job_id: uuid.UUID,
        source: str,
        action: str,
        external_id: str | None = None,
        external_url: str | None = None,
        raw_data: dict | None = None,
    ) -> DiscoverySource:
        record = DiscoverySource(
            company_id=company_id,
            job_id=job_id,
            source=source,
            action=action,
            external_id=external_id,
            external_url=external_url,
            raw_data=raw_data,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_for_company(self, company_id: uuid.UUID) -> list[DiscoverySource]:
        result = await self.session.execute(
            select(DiscoverySource)
            .where(DiscoverySource.company_id == company_id)
            .order_by(DiscoverySource.created_at.desc())
        )
        return list(result.scalars().all())
