"""
Atlas - User Repository
========================
Repository pour les opérations de base de données liées aux utilisateurs.
"""

from sqlalchemy import select

from app.models.user import AuthProvider, User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository dédié aux utilisateurs."""

    model = User

    async def get_by_email(self, email: str) -> User | None:
        """Récupère un utilisateur par email. Insensible à la casse."""
        result = await self.session.execute(
            select(User).where(
                User.email == email.lower(),
                User.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_by_oauth(self, provider: AuthProvider, provider_id: str) -> User | None:
        """Récupère un utilisateur par son identifiant OAuth."""
        result = await self.session.execute(
            select(User).where(
                User.auth_provider == provider,
                User.oauth_provider_id == provider_id,
                User.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        """Vérifie si un email est déjà utilisé."""
        return await self.get_by_email(email) is not None
