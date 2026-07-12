"""
Atlas - User Model
==================
Modèle utilisateur. Supporte l'authentification locale + OAuth (Google, GitHub).
"""

import uuid
from enum import StrEnum

from sqlalchemy import Boolean, Enum, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AtlasBase


class UserRole(StrEnum):
    USER = "user"
    ANALYST = "analyst"
    ADMIN = "admin"


class AuthProvider(StrEnum):
    LOCAL = "local"
    GOOGLE = "google"
    GITHUB = "github"


class User(AtlasBase):
    """
    Représente un utilisateur de la plateforme Atlas.

    Supporte trois modes d'authentification :
    - LOCAL : email + mot de passe hashé Argon2id
    - GOOGLE : OAuth Google
    - GITHUB : OAuth GitHub

    La colonne hashed_password est nullable pour permettre OAuth sans mot de passe.
    """

    __tablename__ = "users"

    # Identité
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Authentification
    hashed_password: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth_provider: Mapped[AuthProvider] = mapped_column(
        Enum(AuthProvider, name="auth_provider_enum", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=AuthProvider.LOCAL,
    )
    oauth_provider_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Rôle et statut
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role_enum", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=UserRole.USER,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Préférences
    preferred_language: Mapped[str] = mapped_column(String(10), default="fr", nullable=False)

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role}>"
