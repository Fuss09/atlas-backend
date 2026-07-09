"""
Atlas - Exception Handlers
===========================
Transforme les exceptions internes en réponses HTTP normalisées.
Jamais de trace Python exposée au frontend.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import (
    AlreadyExistsError,
    AtlasError,
    AuthenticationError,
    DatabaseError,
    ExternalServiceError,
    InvalidCredentialsError,
    InvalidTokenError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    TokenExpiredError,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    """Format standardisé pour toutes les erreurs."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
                "timestamp": datetime.now(UTC).isoformat(),
            }
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Enregistre tous les handlers d'exceptions sur l'application FastAPI."""

    @app.exception_handler(TokenExpiredError)
    async def handle_token_expired(request: Request, exc: TokenExpiredError) -> JSONResponse:
        return _error_response(401, exc.code, exc.message)

    @app.exception_handler(InvalidTokenError)
    async def handle_invalid_token(request: Request, exc: InvalidTokenError) -> JSONResponse:
        return _error_response(401, exc.code, exc.message)

    @app.exception_handler(InvalidCredentialsError)
    async def handle_invalid_credentials(
        request: Request, exc: InvalidCredentialsError
    ) -> JSONResponse:
        return _error_response(401, exc.code, exc.message)

    @app.exception_handler(AuthenticationError)
    async def handle_auth_error(request: Request, exc: AuthenticationError) -> JSONResponse:
        return _error_response(401, exc.code, exc.message)

    @app.exception_handler(PermissionDeniedError)
    async def handle_permission_denied(
        request: Request, exc: PermissionDeniedError
    ) -> JSONResponse:
        return _error_response(403, exc.code, exc.message)

    @app.exception_handler(NotFoundError)
    async def handle_not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return _error_response(404, exc.code, exc.message, exc.details)

    @app.exception_handler(AlreadyExistsError)
    async def handle_already_exists(request: Request, exc: AlreadyExistsError) -> JSONResponse:
        return _error_response(409, exc.code, exc.message, exc.details)

    @app.exception_handler(RateLimitError)
    async def handle_rate_limit(request: Request, exc: RateLimitError) -> JSONResponse:
        return _error_response(429, exc.code, exc.message)

    @app.exception_handler(ExternalServiceError)
    async def handle_external_service(
        request: Request, exc: ExternalServiceError
    ) -> JSONResponse:
        logger.error("External service error", error=exc.message, details=exc.details)
        return _error_response(502, exc.code, "External service temporarily unavailable")

    @app.exception_handler(DatabaseError)
    async def handle_database_error(request: Request, exc: DatabaseError) -> JSONResponse:
        logger.error("Database error", error=exc.message)
        return _error_response(500, "DatabaseError", "A database error occurred")

    @app.exception_handler(AtlasError)
    async def handle_atlas_error(request: Request, exc: AtlasError) -> JSONResponse:
        logger.warning("Atlas error", code=exc.code, message=exc.message)
        return _error_response(500, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Erreurs de validation Pydantic — format normalisé."""
        errors = [
            {
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
            for error in exc.errors()
        ]
        return _error_response(
            422,
            "ValidationError",
            "Request validation failed",
            {"errors": errors},
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return _error_response(exc.status_code, "HTTPError", exc.detail or "HTTP error")

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        """
        Handler de dernier recours.
        Log l'erreur complète côté serveur, mais ne l'expose JAMAIS au client.
        """
        logger.error(
            "Unexpected error",
            exc_info=exc,
            path=request.url.path,
            method=request.method,
        )
        return _error_response(500, "InternalError", "An unexpected error occurred")
