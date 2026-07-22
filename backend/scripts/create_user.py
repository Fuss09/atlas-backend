"""
Atlas - Create User
===================
Crée un compte avec un rôle choisi (le seul chemin pour créer un admin).
Le mot de passe est demandé en saisie interactive — jamais en argument.

Usage :
    python -m scripts.create_user --email you@example.com --name "You" --role admin
"""
import argparse
import asyncio
import getpass

from app.models import (  # noqa: F401
    catalyst, company, discovery, event, graph, opportunity, snapshot, theme, user, watchlist,
)
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.db.database import AsyncSessionFactory
from app.models.user import AuthProvider, User, UserRole
from app.repositories.user import UserRepository

logger = get_logger(__name__)


async def create(email: str, name: str, role: str, password: str) -> None:
    email = email.strip().lower()
    try:
        role_enum = UserRole(role)
    except ValueError:
        logger.error("Invalid role", role=role, valid=[r.value for r in UserRole])
        return

    async with AsyncSessionFactory() as session:
        repo = UserRepository(session)
        if await repo.email_exists(email):
            logger.error("Email already exists", email=email)
            return
        user = await repo.create(
            email=email,
            name=name,
            hashed_password=hash_password(password),
            auth_provider=AuthProvider.LOCAL,
            role=role_enum,
            is_active=True,
            is_verified=True,
        )
        await session.commit()
        logger.info("User created", user_id=str(user.id), email=email, role=role_enum.value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a user account")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", default="user", choices=["user", "analyst", "admin"])
    args = parser.parse_args()
    configure_logging()

    password = getpass.getpass("Password (8+ chars, 1 uppercase, 1 digit): ")
    if len(password) < 8 or not any(c.isupper() for c in password) or not any(c.isdigit() for c in password):
        print("Password too weak — need 8+ chars, at least 1 uppercase and 1 digit.")
        return
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.")
        return

    asyncio.run(create(args.email, args.name, args.role, password))


if __name__ == "__main__":
    main()
