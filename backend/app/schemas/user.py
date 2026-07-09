"""
Atlas - User Schemas
====================
Schémas Pydantic v2 pour la validation des données utilisateur.
Séparation stricte entre : données d'entrée, données de sortie, données internes.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import AuthProvider, UserRole


class UserBase(BaseModel):
    """Champs communs à tous les schémas utilisateur."""

    email: EmailStr
    name: str = Field(min_length=2, max_length=255)


class UserCreate(UserBase):
    """
    Données requises pour créer un compte local.
    Le mot de passe est validé ici puis hashé dans le service.
    """

    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Valide la complexité minimale du mot de passe."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserResponse(UserBase):
    """
    Données retournées au frontend.
    Ne contient JAMAIS le hashed_password ou les tokens.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: UserRole
    is_active: bool
    is_verified: bool
    auth_provider: AuthProvider
    avatar_url: str | None = None
    preferred_language: str
    created_at: datetime
    updated_at: datetime


class UserUpdate(BaseModel):
    """Champs modifiables par l'utilisateur lui-même."""

    name: str | None = Field(default=None, min_length=2, max_length=255)
    preferred_language: str | None = Field(default=None, min_length=2, max_length=10)


# ─── Auth Schemas ─────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    """Données de connexion."""

    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    """Tokens retournés après authentification réussie."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Requête de rafraîchissement du token."""

    refresh_token: str


class RegisterRequest(UserCreate):
    """Alias explicite pour l'endpoint d'inscription."""
    pass
