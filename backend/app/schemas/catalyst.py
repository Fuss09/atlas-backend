"""
Atlas - Catalyst Schemas
========================
"""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CatalystCompanyRef(BaseModel):
    """Référence légère vers l'entreprise, pour l'affichage calendrier."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    ticker: str | None
    sector: str | None


class CatalystCreate(BaseModel):
    """Corps de POST /catalysts (ajout manuel)."""

    company_id: uuid.UUID
    catalyst_type: Literal[
        "clinical_readout",
        "earnings",
        "regulatory_decision",
        "conference",
        "product_launch",
        "lockup_expiry",
        "other",
    ]
    title: str = Field(min_length=3, max_length=300)
    description: str | None = Field(default=None, max_length=1000)
    expected_date: date
    date_precision: Literal["day", "month", "quarter"] = "day"
    source_url: str | None = Field(default=None, max_length=500)


class CatalystResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    catalyst_type: str
    title: str
    description: str | None
    expected_date: date
    date_precision: str
    status: str
    source: str
    source_url: str | None
    created_at: datetime
    company: CatalystCompanyRef
