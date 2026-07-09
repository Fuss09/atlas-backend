"""
Atlas - Base Model
==================
Modèle de base dont héritent tous les modèles SQLAlchemy.

Principe : toutes les entités ont un UUID, des timestamps et un soft delete.
Jamais de suppression physique en production — chaque modification crée un historique.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class TimestampMixin:
    """Ajoute created_at et updated_at à un modèle."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """
    Ajoute la capacité de soft delete.
    Les objets supprimés ne sont pas physiquement effacés — ils sont marqués deleted_at.
    Cela préserve l'historique complet, essentiel pour le ML et le backtesting.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    def soft_delete(self) -> None:
        """Marque l'entité comme supprimée."""
        self.deleted_at = datetime.now(UTC)
        self.is_deleted = True

    def restore(self) -> None:
        """Restaure une entité supprimée."""
        self.deleted_at = None
        self.is_deleted = False


class AtlasBase(Base, TimestampMixin, SoftDeleteMixin):
    """
    Classe de base pour tous les modèles Atlas.
    Fournit : UUID primaire, timestamps, soft delete.
    """

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    def to_dict(self) -> dict:
        """Convertit le modèle en dictionnaire (utile pour les logs)."""
        return {
            col.name: getattr(self, col.name)
            for col in self.__table__.columns
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.id}>"
