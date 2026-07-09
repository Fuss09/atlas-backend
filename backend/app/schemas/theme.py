"""
Atlas - Theme Schemas
=====================
Schémas Pydantic v2 pour les thèmes d'investissement.
"""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.theme import MaturityLevel
from app.schemas.company import CompanyListItem, PaginatedResponse


# ─── Helpers ──────────────────────────────────────────────────────────────────

_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _generate_theme_slug(name: str) -> str:
    """Génère un slug depuis un nom de thème."""
    try:
        from unidecode import unidecode
        name = unidecode(name)
    except ImportError:
        pass
    slug = name.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")[:170]


# ─── Schémas d'entrée ─────────────────────────────────────────────────────────

class ThemeCreate(BaseModel):
    """Données pour créer un thème."""

    name: str = Field(min_length=2, max_length=150)
    slug: str | None = Field(default=None, max_length=180)
    description: str | None = Field(default=None, max_length=2000)
    category: str | None = Field(default=None, max_length=100)
    maturity_level: MaturityLevel = Field(default=MaturityLevel.EMERGING)
    color: str | None = Field(default=None, max_length=7)
    icon: str | None = Field(default=None, max_length=50)
    is_active: bool = Field(default=True)

    @model_validator(mode="after")
    def generate_slug_if_missing(self) -> "ThemeCreate":
        if not self.slug:
            self.slug = _generate_theme_slug(self.name)
        return self

    @field_validator("color")
    @classmethod
    def validate_hex_color(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not _HEX_COLOR_RE.match(v):
            raise ValueError("Color must be a valid hex code (ex: #6366f1)")
        return v.lower()


class ThemeUpdate(BaseModel):
    """Mise à jour partielle d'un thème. Tous les champs optionnels."""

    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    category: str | None = Field(default=None, max_length=100)
    maturity_level: MaturityLevel | None = Field(default=None)
    color: str | None = Field(default=None, max_length=7)
    icon: str | None = Field(default=None, max_length=50)
    is_active: bool | None = Field(default=None)

    @field_validator("color")
    @classmethod
    def validate_hex_color(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not _HEX_COLOR_RE.match(v):
            raise ValueError("Color must be a valid hex code (ex: #6366f1)")
        return v.lower()


# ─── Schémas de sortie ────────────────────────────────────────────────────────

class ThemeResponse(BaseModel):
    """Représentation complète d'un thème."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    category: str | None
    maturity_level: MaturityLevel
    color: str | None
    icon: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Calculé par le service — nombre d'entreprises associées
    companies_count: int = 0


class ThemeListItem(BaseModel):
    """Version allégée pour les listes."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    category: str | None
    maturity_level: MaturityLevel
    color: str | None
    icon: str | None
    is_active: bool
    companies_count: int = 0


class ThemeWithCompanies(ThemeResponse):
    """Thème avec la liste paginée de ses entreprises."""

    companies: PaginatedResponse[CompanyListItem]


# ─── Association schemas ───────────────────────────────────────────────────────

class CompanyThemeLink(BaseModel):
    """Payload pour associer/dissocier une entreprise à un thème."""

    company_id: uuid.UUID
