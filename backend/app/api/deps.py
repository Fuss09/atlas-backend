"""
Atlas - API Dependencies
========================
Dependencies FastAPI réutilisables dans tous les endpoints.
"""

import uuid
from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AuthenticationError, InvalidTokenError, TokenExpiredError
from app.core.security import TokenType, decode_token
from app.db.database import DbSession
from app.models.user import User
from app.services.user import UserService

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_user_service(db: DbSession) -> UserService:
    """Fournit un UserService avec la session de base de données."""
    return UserService(db)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    user_service: UserServiceDep,
) -> User:
    """
    Extrait et valide le token JWT du header Authorization.
    Retourne l'utilisateur authentifié.

    Raises:
        AuthenticationError: Si aucun token n'est fourni.
        TokenExpiredError: Si le token a expiré.
        InvalidTokenError: Si le token est invalide.
    """
    if not credentials:
        raise AuthenticationError("Authentication required")

    try:
        payload = decode_token(credentials.credentials, expected_type=TokenType.ACCESS)
        user_id = uuid.UUID(payload["sub"])
    except (TokenExpiredError, InvalidTokenError):
        raise
    except Exception as exc:
        raise InvalidTokenError("Could not validate credentials") from exc

    return await user_service.get_by_id(user_id)


CurrentUser = Annotated[User, Depends(get_current_user)]


class PaginationParams:
    """Paramètres de pagination standardisés pour tous les endpoints de liste."""

    def __init__(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> None:
        self.page = max(1, page)
        self.page_size = min(max(1, page_size), 100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


Pagination = Annotated[PaginationParams, Depends(PaginationParams)]
