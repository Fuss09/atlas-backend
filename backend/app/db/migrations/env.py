"""
Atlas - Alembic Configuration
================================
Configuration d'Alembic pour les migrations async avec SQLAlchemy 2.

Important : Alembic utilise le driver psycopg2 (sync) pour les migrations,
même si l'application utilise asyncpg en runtime.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import des modèles pour l'autogenerate
from app.db.database import Base
from app.models import user  # noqa: F401 — importer tous les modèles ici
from app.models import company  # noqa: F401
from app.models import theme  # noqa: F401
from app.models import discovery  # noqa: F401
from app.models import event  # noqa: F401
from app.models import opportunity  # noqa: F401
from app.models import graph  # noqa: F401
from app.core.config import get_settings

config = context.config
settings = get_settings()

# Injection de l'URL depuis les settings (pas depuis alembic.ini)
config.set_main_option("sqlalchemy.url", settings.database.sync_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Migrations en mode offline (sans connexion à la DB).
    Génère uniquement le SQL.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Migrations en mode online (avec connexion à la DB)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
