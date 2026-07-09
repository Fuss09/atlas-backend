"""
Atlas - Base Repository
========================
Pattern Repository générique avec SQLAlchemy 2 async.
Chaque modèle aura son propre Repository qui hérite de ce BaseRepository.

Avantages :
- Logique de base de données centralisée et testable
- Les services ne connaissent pas SQLAlchemy
- Facilite le mock en tests
"""

import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import AtlasBase

ModelType = TypeVar("ModelType", bound=AtlasBase)


class BaseRepository(Generic[ModelType]):
    """
    Repository de base fournissant les opérations CRUD.

    Usage:
        class UserRepository(BaseRepository[User]):
            model = User
    """

    model: type[ModelType]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, entity_id: uuid.UUID) -> ModelType | None:
        """Récupère une entité par son UUID. Exclut les soft-deleted."""
        result = await self.session.execute(
            select(self.model).where(
                self.model.id == entity_id,
                self.model.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_by_ids(self, entity_ids: list[uuid.UUID]) -> list[ModelType]:
        """
        Récupère plusieurs entités en une seule requête (évite les N+1).
        Utilisé par les services qui enrichissent une liste paginée avec
        des données d'une entité liée — ex: EventListItem avec le nom
        de l'entreprise, une seule requête pour toute la page plutôt
        qu'une par event.
        """
        if not entity_ids:
            return []
        result = await self.session.execute(
            select(self.model).where(
                self.model.id.in_(entity_ids),
                self.model.is_deleted == False,  # noqa: E712
            )
        )
        return list(result.scalars().all())

    async def get_all(
        self,
        offset: int = 0,
        limit: int = 50,
        filters: dict[str, Any] | None = None,
    ) -> list[ModelType]:
        """
        Récupère une liste paginée d'entités.

        Args:
            offset: Position de départ.
            limit: Nombre maximum de résultats (max 100).
            filters: Filtres additionnels sous forme de dict {colonne: valeur}.
        """
        limit = min(limit, 100)  # Hard limit pour éviter les abus

        stmt = select(self.model).where(self.model.is_deleted == False)  # noqa: E712

        if filters:
            for field, value in filters.items():
                stmt = stmt.where(getattr(self.model, field) == value)

        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, **kwargs: Any) -> ModelType:
        """Crée et persiste une nouvelle entité."""
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()  # Pour obtenir l'ID sans commit
        await self.session.refresh(instance)
        return instance

    async def update(self, entity_id: uuid.UUID, **kwargs: Any) -> ModelType | None:
        """Met à jour une entité existante."""
        instance = await self.get_by_id(entity_id)
        if not instance:
            return None

        for field, value in kwargs.items():
            if hasattr(instance, field) and value is not None:
                setattr(instance, field, value)

        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def soft_delete(self, entity_id: uuid.UUID) -> bool:
        """Soft delete d'une entité. Retourne True si l'entité existait."""
        instance = await self.get_by_id(entity_id)
        if not instance:
            return False

        instance.soft_delete()
        await self.session.flush()
        return True

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        """Compte le nombre d'entités actives."""
        from sqlalchemy import func

        stmt = (
            select(func.count())
            .select_from(self.model)
            .where(self.model.is_deleted == False)  # noqa: E712
        )

        if filters:
            for field, value in filters.items():
                stmt = stmt.where(getattr(self.model, field) == value)

        result = await self.session.execute(stmt)
        return result.scalar_one()
