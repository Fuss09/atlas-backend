"""
Atlas - Logging
===============
Logging structuré avec structlog.
Chaque log contient request_id, user_id, et execution_time.
Format JSON en production, format coloré en développement.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from app.core.config import get_settings


def add_app_context(
    logger: logging.Logger,
    method: str,
    event_dict: EventDict,
) -> EventDict:
    """Ajoute le contexte de l'application à chaque log."""
    settings = get_settings()
    event_dict["app"] = settings.app_name
    event_dict["version"] = settings.app_version
    event_dict["environment"] = settings.environment
    return event_dict


def drop_color_message_key(
    logger: logging.Logger,
    method: str,
    event_dict: EventDict,
) -> EventDict:
    """Supprime la clé color_message ajoutée par uvicorn."""
    event_dict.pop("color_message", None)
    return event_dict


def configure_logging() -> None:
    """
    Configure le système de logging.
    - Développement : format humain lisible avec couleurs
    - Production : format JSON structuré (compatible avec Loki, Datadog, etc.)
    """
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        add_app_context,
        drop_color_message_key,
    ]

    if settings.is_production:
        processors: list[Processor] = [
            *shared_processors,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Intercepter aussi les logs stdlib (uvicorn, sqlalchemy, etc.)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def get_logger(name: str | None = None) -> Any:
    """Retourne un logger structlog."""
    return structlog.get_logger(name)
