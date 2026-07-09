"""Atlas - Discovery Schemas"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.discovery import DiscoverySourceName, JobStatus


class TriggerJobRequest(BaseModel):
    source: DiscoverySourceName
    params: dict = Field(default_factory=dict)


class DiscoveryJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    status: JobStatus
    triggered_by: uuid.UUID | None
    started_at: datetime | None
    finished_at: datetime | None
    companies_found: int
    companies_created: int
    companies_updated: int
    companies_skipped: int
    errors: list | None
    params: dict | None
    meta: dict | None
    created_at: datetime
    duration_seconds: float | None = None


class DiscoveryJobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    status: JobStatus
    companies_found: int
    companies_created: int
    companies_updated: int
    created_at: datetime
    duration_seconds: float | None = None


class AvailableSource(BaseModel):
    source: str
    collector: str | None
    implemented: bool
