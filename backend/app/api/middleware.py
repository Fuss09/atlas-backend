"""
Atlas - Middleware
==================
Middleware de logging des requêtes HTTP.
Chaque requête reçoit un request_id unique, loggé avec le temps d'exécution.
"""

import time
import uuid
from collections.abc import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Log toutes les requêtes entrantes avec :
    - request_id unique (UUID v4)
    - method, path, status_code
    - durée d'exécution en ms
    - user_id si disponible dans le contexte

    Le request_id est également retourné dans les headers de réponse
    pour faciliter le débogage côté client.
    """

    EXCLUDED_PATHS = {"/health", "/ready", "/metrics"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Générer un ID unique pour cette requête
        request_id = str(uuid.uuid4())
        start_time = time.perf_counter()

        # Injecter dans le contexte structlog (disponible dans tous les logs de cette requête)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        # Stocker le request_id pour que les handlers puissent y accéder
        request.state.request_id = request_id

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            if request.url.path not in self.EXCLUDED_PATHS:
                logger.error(
                    "Request failed",
                    duration_ms=duration_ms,
                    error=str(exc),
                )
            raise

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        if request.url.path not in self.EXCLUDED_PATHS:
            log_fn = logger.warning if response.status_code >= 400 else logger.info
            log_fn(
                "Request completed",
                status_code=response.status_code,
                duration_ms=duration_ms,
            )

        # Ajouter le request_id dans la réponse
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms}ms"

        return response
