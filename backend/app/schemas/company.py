"""
Atlas - Company Schemas
=======================
Séparation stricte entre :
- CompanyCreate     : données d'entrée à la création
- CompanyUpdate     : données modifiables (tous optionnels)
- CompanyResponse   : données retournées à l'API (safe, jamais de champs internes)
- CompanyListItem   : version allégée pour les listes (économise la bande passante)
- CompanySearchParams : paramètres de recherche et filtrage
- PaginatedResponse : enveloppe de pagination générique (réutilisable)
"""

import re
import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.models.company import CompanyStatus, CompanyType

DataT = TypeVar("DataT")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _generate_slug(name: str) -> str:
    """
    Génère un slug URL-friendly depuis un nom d'entreprise.
    Ex: "NVIDIA Corporation" → "nvidia-corporation"
        "Société Générale" → "societe-generale"
    """
    try:
        from unidecode import unidecode
        name = unidecode(name)
    except ImportError:
        pass

    slug = name.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")[:280]


# ─── Base partagé ─────────────────────────────────────────────────────────────

class CompanyBase(BaseModel):
    """Champs communs à Create et Update."""

    name: str = Field(min_length=1, max_length=255)
    legal_name: str | None = Field(default=None, max_length=500)
    ticker: str | None = Field(default=None, max_length=20)
    isin: str | None = Field(default=None)
    exchange: str | None = Field(default=None, max_length=50)
    cusip: str | None = Field(default=None, max_length=9)
    company_type: CompanyType = Field(default=CompanyType.PUBLIC)
    status: CompanyStatus = Field(default=CompanyStatus.ACTIVE)
    sector: str | None = Field(default=None, max_length=100)
    industry: str | None = Field(default=None, max_length=150)
    sic_code: str | None = Field(default=None, max_length=10)
    country: str = Field(min_length=2, max_length=2)
    country_name: str | None = Field(default=None, max_length=100)
    headquarters_city: str | None = Field(default=None, max_length=100)
    headquarters_state: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None)
    description_short: str | None = Field(default=None, max_length=500)
    website: str | None = Field(default=None, max_length=512)
    logo_url: str | None = Field(default=None, max_length=512)
    founded_year: int | None = Field(default=None, ge=1600, le=2100)
    ipo_date: date | None = Field(default=None)
    market_cap_usd: int | None = Field(default=None, ge=0)
    employees: int | None = Field(default=None, ge=0)
    revenue_usd: int | None = Field(default=None, ge=0)
    tags: list[str] | None = Field(default=None)
    data_sources: dict[str, Any] | None = Field(default=None)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, v: str | None) -> str | None:
        """Normalise le ticker en majuscules."""
        return v.upper().strip() if v else None

    @field_validator("isin")
    @classmethod
    def validate_isin(cls, v: str | None) -> str | None:
        """Valide le format ISIN : 2 lettres pays + 9 alphanumériques + 1 chiffre."""
        if v is None:
            return None
        v = v.upper().strip()
        if not re.match(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$", v):
            raise ValueError("ISIN must be 12 characters: 2 letters + 9 alphanumeric + 1 digit")
        return v

    @field_validator("country")
    @classmethod
    def normalize_country(cls, v: str) -> str:
        """Normalise le code pays en majuscules."""
        return v.upper().strip()

    @field_validator("website")
    @classmethod
    def normalize_website(cls, v: str | None) -> str | None:
        """Ajoute https:// si le schéma est absent."""
        if not v:
            return None
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            v = f"https://{v}"
        return v


# ─── Schémas d'entrée ─────────────────────────────────────────────────────────

class CompanyCreate(CompanyBase):
    """
    Données requises pour créer une entreprise.
    Le slug est généré automatiquement si non fourni.
    """

    slug: str | None = Field(
        default=None,
        max_length=300,
        description="Généré automatiquement depuis le nom si non fourni",
    )

    @model_validator(mode="after")
    def generate_slug_if_missing(self) -> "CompanyCreate":
        if not self.slug:
            self.slug = _generate_slug(self.name)
        return self


class CompanyUpdate(BaseModel):
    """
    Données modifiables par un administrateur.
    Tous les champs sont optionnels — seuls les champs fournis sont mis à jour.

    Note : le slug n'est pas directement modifiable pour préserver les URLs.
    Un endpoint dédié /companies/{id}/slug pourra être ajouté si nécessaire.
    """

    name: str | None = Field(default=None, min_length=1, max_length=255)
    legal_name: str | None = Field(default=None, max_length=500)
    ticker: str | None = Field(default=None, max_length=20)
    isin: str | None = Field(default=None)
    exchange: str | None = Field(default=None, max_length=50)
    company_type: CompanyType | None = Field(default=None)
    status: CompanyStatus | None = Field(default=None)
    sector: str | None = Field(default=None, max_length=100)
    industry: str | None = Field(default=None, max_length=150)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    country_name: str | None = Field(default=None, max_length=100)
    headquarters_city: str | None = Field(default=None, max_length=100)
    headquarters_state: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None)
    description_short: str | None = Field(default=None, max_length=500)
    website: str | None = Field(default=None, max_length=512)
    logo_url: str | None = Field(default=None, max_length=512)
    founded_year: int | None = Field(default=None, ge=1600, le=2100)
    ipo_date: date | None = Field(default=None)
    market_cap_usd: int | None = Field(default=None, ge=0)
    employees: int | None = Field(default=None, ge=0)
    revenue_usd: int | None = Field(default=None, ge=0)
    tags: list[str] | None = Field(default=None)
    is_featured: bool | None = Field(default=None)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, v: str | None) -> str | None:
        return v.upper().strip() if v else None

    @field_validator("country")
    @classmethod
    def normalize_country(cls, v: str | None) -> str | None:
        return v.upper().strip() if v else None

    @field_validator("isin")
    @classmethod
    def validate_isin(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.upper().strip()
        if not re.match(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$", v):
            raise ValueError("ISIN must be 12 characters: 2 letters + 9 alphanumeric + 1 digit")
        return v


# ─── Schémas de sortie ────────────────────────────────────────────────────────

class CompanyResponse(BaseModel):
    """
    Représentation complète d'une entreprise retournée par l'API.
    Inclut tous les champs calculés et les métadonnées.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    legal_name: str | None
    ticker: str | None
    isin: str | None
    exchange: str | None
    cusip: str | None
    company_type: CompanyType
    status: CompanyStatus
    sector: str | None
    industry: str | None
    sic_code: str | None
    country: str
    country_name: str | None
    headquarters_city: str | None
    headquarters_state: str | None
    description: str | None
    description_short: str | None
    website: str | None
    logo_url: str | None
    founded_year: int | None
    ipo_date: date | None
    market_cap_usd: int | None
    employees: int | None
    revenue_usd: int | None
    atlas_score: int | None
    is_featured: bool
    tags: list[str] | None
    data_sources: dict[str, Any] | None

    # Timestamps
    created_at: datetime
    updated_at: datetime

    # Relations futures (None jusqu'à leur implémentation)
    # Ces champs seront peuplés par les modules suivants :
    # themes_count: int = 0          — Module 04
    # technologies_count: int = 0    — Module 04
    # events_count: int = 0          — Module 03
    # latest_story_id: uuid.UUID | None = None  — Module 06


class CompanyListItem(BaseModel):
    """
    Version allégée pour les listes.
    Évite de transmettre la description complète sur chaque item.
    Optimisé pour le dashboard et les résultats de recherche.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    ticker: str | None
    exchange: str | None
    company_type: CompanyType
    status: CompanyStatus
    sector: str | None
    country: str
    market_cap_usd: int | None
    employees: int | None
    atlas_score: int | None
    is_featured: bool
    logo_url: str | None
    description_short: str | None
    tags: list[str] | None
    updated_at: datetime


# ─── Pagination générique ─────────────────────────────────────────────────────

class PaginatedResponse(BaseModel, Generic[DataT]):
    """
    Enveloppe de pagination réutilisable pour tous les endpoints de liste.

    Usage dans un endpoint :
        return PaginatedResponse[CompanyListItem](
            items=[...],
            total=count,
            page=params.page,
            page_size=params.page_size,
        )
    """

    items: list[DataT]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        if self.page_size == 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    model_config = ConfigDict(
        # Permet d'inclure les @property dans la sérialisation
        populate_by_name=True,
    )


# ─── Paramètres de recherche ──────────────────────────────────────────────────

class CompanySortOption(StrEnum):
    """
    Options de tri exposées par GET /companies.
    RELEVANCE reproduit le tri historique (featured > score > market cap > nom),
    conservé comme défaut pour ne pas changer le comportement existant.
    """

    RELEVANCE = "relevance"
    NAME_ASC = "name_asc"
    NAME_DESC = "name_desc"
    MARKET_CAP_DESC = "market_cap_desc"
    MARKET_CAP_ASC = "market_cap_asc"
    SCORE_DESC = "score_desc"
    SCORE_ASC = "score_asc"
    FOUNDED_DESC = "founded_desc"
    RECENTLY_UPDATED = "recently_updated"


class CompanySearchParams(BaseModel):
    """
    Paramètres de recherche et filtrage pour les listes de sociétés.
    Utilisé comme query params dans GET /companies.

    Design : tous les champs sont optionnels et combinables.
    Exemple : ?q=nvidia&sector=Technology&country=US&company_type=public&sort=market_cap_desc
    """

    q: str | None = Field(
        default=None,
        max_length=200,
        description="Recherche textuelle (nom, ticker, description)",
    )
    sector: str | None = Field(default=None, max_length=100)
    industry: str | None = Field(default=None, max_length=150)
    country: str | None = Field(default=None, max_length=2)
    company_type: CompanyType | None = Field(default=None)
    status: CompanyStatus | None = Field(default=CompanyStatus.ACTIVE)
    exchange: str | None = Field(default=None, max_length=50)
    is_featured: bool | None = Field(default=None)
    min_market_cap: int | None = Field(default=None, ge=0)
    max_market_cap: int | None = Field(default=None, ge=0)
    min_atlas_score: int | None = Field(default=None, ge=0, le=100)
    tags: list[str] | None = Field(default=None)
    sort: CompanySortOption = Field(default=CompanySortOption.RELEVANCE)

    @field_validator("country")
    @classmethod
    def normalize_country(cls, v: str | None) -> str | None:
        return v.upper().strip() if v else None
