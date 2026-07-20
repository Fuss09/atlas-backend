"""
Atlas - Company Import Schemas
==============================
"""

from pydantic import BaseModel, Field


class CompanyImportRequest(BaseModel):
    """Corps de POST /companies/import."""

    ticker: str = Field(min_length=1, max_length=20, description="Ex: ABVX, NVDA")
    exchange: str | None = Field(
        default=None,
        max_length=50,
        description="Place de cotation (EURONEXT PARIS, NASDAQ…) — sert au suffixe symbole",
    )
