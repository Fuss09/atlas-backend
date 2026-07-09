"""
Atlas - Database
================
Gestion des connexions PostgreSQL via SQLAlchemy 2 en mode async.
Pool de connexions configuré pour la production.
"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _create_engine(test_mode: bool = False):
    """
    Crée le moteur SQLAlchemy async.

    Args:
        test_mode: Si True, utilise NullPool (nécessaire pour les tests avec pytest-asyncio).
    """
    settings = get_settings()

    engine_kwargs = {
        "echo": settings.database.echo,
        "echo_pool": settings.is_development,
    }

    if test_mode:
        engine_kwargs["poolclass"] = NullPool
    else:
        engine_kwargs.update(
            {
                "pool_size": settings.database.pool_size,
                "max_overflow": settings.database.max_overflow,
                "pool_timeout": settings.database.pool_timeout,
                "pool_pre_ping": True,  # Vérifie la connexion avant utilisation
            }
        )

    return create_async_engine(settings.database.url, **engine_kwargs)


# Moteur principal
_engine = _create_engine()

# Session factory
AsyncSessionFactory = async_sessionmaker(
    bind=_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """
    Classe de base pour tous les modèles SQLAlchemy.
    Fournit des colonnes communes à tous les modèles.
    """
    pass


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency FastAPI qui fournit une session de base de données.
    La session est fermée automatiquement après la requête.
    En cas d'erreur, le rollback est effectué automatiquement.

    Usage:
        @router.get("/")
        async def endpoint(db: DbSession) -> ...:
            ...
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Type annoté pour FastAPI Depends
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


async def check_database_connection() -> bool:
    """Vérifie que la base de données est accessible."""
    try:
        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("Database health check failed", error=str(exc))
        return False
