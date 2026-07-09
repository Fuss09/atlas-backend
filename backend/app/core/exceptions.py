"""
Atlas - Exceptions
==================
Hiérarchie d'exceptions métier d'Atlas.

Principe : jamais de trace Python exposée au frontend.
Chaque exception est mappée vers un code HTTP précis dans les handlers.
"""

from typing import Any


class AtlasError(Exception):
    """Exception de base pour toutes les erreurs d'Atlas."""

    def __init__(
        self,
        message: str,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}


# ─── Authentification ─────────────────────────────────────────────────────────

class AuthenticationError(AtlasError):
    """Erreur d'authentification générique (401)."""


class InvalidCredentialsError(AuthenticationError):
    """Identifiants invalides."""


class TokenExpiredError(AuthenticationError):
    """Token JWT expiré."""


class InvalidTokenError(AuthenticationError):
    """Token JWT invalide ou malformé."""


# ─── Autorisation ─────────────────────────────────────────────────────────────

class PermissionDeniedError(AtlasError):
    """Action non autorisée pour cet utilisateur (403)."""


# ─── Ressources ───────────────────────────────────────────────────────────────

class NotFoundError(AtlasError):
    """Ressource introuvable (404)."""

    def __init__(self, resource: str, identifier: Any) -> None:
        super().__init__(
            message=f"{resource} not found",
            details={"resource": resource, "identifier": str(identifier)},
        )


class AlreadyExistsError(AtlasError):
    """Ressource déjà existante (409)."""

    def __init__(self, resource: str, field: str, value: Any) -> None:
        super().__init__(
            message=f"{resource} with {field}={value!r} already exists",
            details={"resource": resource, "field": field, "value": str(value)},
        )


# ─── Validation ───────────────────────────────────────────────────────────────

class ValidationError(AtlasError):
    """Erreur de validation métier (422)."""


# ─── Infrastructure ───────────────────────────────────────────────────────────

class DatabaseError(AtlasError):
    """Erreur de base de données (500)."""


class CacheError(AtlasError):
    """Erreur Redis (500)."""


class MessageBrokerError(AtlasError):
    """Erreur RabbitMQ (500)."""


class GraphDatabaseError(AtlasError):
    """Erreur Neo4j (500)."""


# ─── Externe ──────────────────────────────────────────────────────────────────

class ExternalServiceError(AtlasError):
    """Erreur d'appel à un service externe (502)."""

    def __init__(self, service: str, message: str) -> None:
        super().__init__(
            message=f"External service error: {service} - {message}",
            details={"service": service},
        )


class RateLimitError(AtlasError):
    """Rate limit atteint (429)."""
