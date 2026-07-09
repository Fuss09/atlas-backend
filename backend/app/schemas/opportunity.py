"""
Atlas - Opportunity Schemas
=============================
"""

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.engines.opportunity import ConvictionLevel, OpportunityStage


class ScoreComponentSchema(BaseModel):
    """Représentation API d'un composant du score — toujours explicable."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    value: float | None = Field(
        description="0 à 100, ou null si le composant n'est pas encore connecté"
    )
    weight: float = Field(description="Part de ce composant dans le score final (0.0 à 1.0)")
    is_connected: bool
    positive_factors: list[str]
    negative_factors: list[str]


class OpportunityScoreResponse(BaseModel):
    """Représentation complète et explicable du score d'une entreprise."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    score: int = Field(ge=0, le=100)
    conviction: ConvictionLevel
    stage: OpportunityStage
    stage_rationale: str
    components: dict[str, ScoreComponentSchema]
    positive_factors: list[str]
    negative_factors: list[str]
    scoring_version: int
    calculated_at: datetime


class OpportunityListItem(BaseModel):
    """Version allégée pour GET /opportunities — une entreprise classée."""

    model_config = ConfigDict(from_attributes=True)

    company_id: uuid.UUID
    company_name: str
    company_slug: str
    company_ticker: str | None = None
    company_sector: str | None = None
    company_country: str | None = None
    company_logo_url: str | None = None
    score: int
    conviction: ConvictionLevel
    stage: OpportunityStage
    calculated_at: datetime


class OpportunitySortOption(StrEnum):
    """Options de tri exposées par GET /opportunities. SCORE_DESC (défaut) préserve le tri historique."""

    SCORE_DESC = "score_desc"
    SCORE_ASC = "score_asc"
    NAME_ASC = "name_asc"
    RECENTLY_CALCULATED = "recently_calculated"


class OpportunitySearchParams(BaseModel):
    """Filtres pour GET /opportunities."""

    min_score: int | None = Field(default=None, ge=0, le=100)
    conviction: ConvictionLevel | None = None
    stage: OpportunityStage | None = None
    sector: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=2)
    theme_id: uuid.UUID | None = None
    sort: OpportunitySortOption = Field(default=OpportunitySortOption.SCORE_DESC)
