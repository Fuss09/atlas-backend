"""
Atlas - User Service
====================
Couche de logique métier pour les utilisateurs.
Le service ne connaît pas FastAPI — il ne manipule que des modèles et des exceptions.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AlreadyExistsError,
    InvalidCredentialsError,
    NotFoundError,
)
from app.core.logging import get_logger
from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import AuthProvider, User
from app.repositories.user import UserRepository
from app.schemas.user import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserUpdate,
)

logger = get_logger(__name__)


class UserService:
    """
    Service gérant les utilisateurs et l'authentification.

    Injecté via la session de base de données, il instancie son propre repository.
    Ce pattern maintient une séparation claire des responsabilités.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = UserRepository(session)

    async def register(self, data: RegisterRequest) -> User:
        """
        Inscrit un nouvel utilisateur avec authentification locale.

        Args:
            data: Données d'inscription validées.

        Returns:
            L'utilisateur créé.

        Raises:
            AlreadyExistsError: Si l'email est déjà utilisé.
        """
        email = data.email.lower()

        if await self.repo.email_exists(email):
            raise AlreadyExistsError("User", "email", email)

        user = await self.repo.create(
            email=email,
            name=data.name,
            hashed_password=hash_password(data.password),
            auth_provider=AuthProvider.LOCAL,
        )

        logger.info("User registered", user_id=str(user.id), email=email)
        return user

    async def login(self, data: LoginRequest) -> TokenResponse:
        """
        Authentifie un utilisateur et retourne une paire de tokens.

        Args:
            data: Email et mot de passe.

        Returns:
            Access token + refresh token.

        Raises:
            InvalidCredentialsError: Si les identifiants sont incorrects.
        """
        user = await self.repo.get_by_email(data.email.lower())

        # Protection anti-timing attack : on vérifie toujours un hash,
        # même si l'utilisateur n'existe pas, pour éviter de révéler
        # l'existence d'un compte via le temps de réponse.
        # verify_password retournera False sur ce hash invalide — c'est le comportement attendu.
        password_hash = user.hashed_password if user else None
        if password_hash is not None:
            password_valid = verify_password(data.password, password_hash)
        else:
            # Simuler le temps de vérification pour éviter le timing attack
            verify_password(data.password, hash_password("__dummy__atlas__timing__"))
            password_valid = False

        if not user or not password_valid or not user.is_active:
            raise InvalidCredentialsError("Invalid email or password")

        if user.auth_provider != AuthProvider.LOCAL:
            raise InvalidCredentialsError(
                f"This account uses {user.auth_provider} authentication"
            )

        logger.info("User logged in", user_id=str(user.id))

        return TokenResponse(
            access_token=create_access_token(str(user.id)),
            refresh_token=create_refresh_token(str(user.id)),
        )

    async def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        """
        Échange un refresh token contre une nouvelle paire de tokens.

        Args:
            refresh_token: Le refresh token JWT valide.

        Returns:
            Nouvelle paire access + refresh token.

        Raises:
            TokenExpiredError: Si le token a expiré.
            InvalidTokenError: Si le token est invalide.
            NotFoundError: Si l'utilisateur n'existe plus.
        """
        payload = decode_token(refresh_token, expected_type=TokenType.REFRESH)
        user_id = uuid.UUID(payload["sub"])

        user = await self.repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise NotFoundError("User", user_id)

        return TokenResponse(
            access_token=create_access_token(str(user_id)),
            refresh_token=create_refresh_token(str(user_id)),
        )

    async def get_by_id(self, user_id: uuid.UUID) -> User:
        """
        Récupère un utilisateur par son ID.

        Raises:
            NotFoundError: Si l'utilisateur n'existe pas.
        """
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        return user

    async def update_profile(self, user_id: uuid.UUID, data: UserUpdate) -> User:
        """Met à jour le profil d'un utilisateur."""
        user = await self.get_by_id(user_id)

        updates = data.model_dump(exclude_none=True)
        if not updates:
            return user

        updated = await self.repo.update(user_id, **updates)
        if not updated:
            raise NotFoundError("User", user_id)

        logger.info("User profile updated", user_id=str(user_id), fields=list(updates.keys()))
        return updated
