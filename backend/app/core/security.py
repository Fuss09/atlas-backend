"""
Atlas - Security
================
Gestion de l'authentification JWT et du hashing des mots de passe.
"""

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from jose import JWTError, jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.config import get_settings
from app.core.exceptions import InvalidTokenError, TokenExpiredError

# Argon2id — meilleur algorithme de hashing actuellement (recommandé par OWASP)
# Supérieur à bcrypt : résistant aux attaques GPU, paramétrable mémoire/CPU
_pwd_hasher = PasswordHash((Argon2Hasher(),))


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


def hash_password(password: str) -> str:
    """Hash un mot de passe avec Argon2id."""
    return _pwd_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie un mot de passe contre son hash Argon2id."""
    return _pwd_hasher.verify(plain_password, hashed_password)


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    """
    Crée un JWT access token.

    Args:
        subject: Identifiant unique de l'utilisateur (user_id).
        extra_claims: Claims additionnels à inclure dans le token.

    Returns:
        Token JWT signé.
    """
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt.access_token_expire_minutes)

    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": TokenType.ACCESS,
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.jwt.secret_key, algorithm=settings.jwt.algorithm)


def create_refresh_token(subject: str) -> str:
    """
    Crée un JWT refresh token.

    Args:
        subject: Identifiant unique de l'utilisateur.

    Returns:
        Token JWT signé avec une expiration longue.
    """
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(days=settings.jwt.refresh_token_expire_days)

    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": TokenType.REFRESH,
        "exp": expire,
        "iat": datetime.now(UTC),
    }

    return jwt.encode(payload, settings.jwt.secret_key, algorithm=settings.jwt.algorithm)


def decode_token(token: str, expected_type: TokenType = TokenType.ACCESS) -> dict[str, Any]:
    """
    Décode et valide un JWT token.

    Args:
        token: Le token JWT à décoder.
        expected_type: Le type attendu (access ou refresh).

    Returns:
        Le payload décodé.

    Raises:
        TokenExpiredError: Si le token a expiré.
        InvalidTokenError: Si le token est invalide ou du mauvais type.
    """
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.jwt.secret_key,
            algorithms=[settings.jwt.algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError("Token has expired") from exc
    except JWTError as exc:
        raise InvalidTokenError("Invalid token") from exc

    token_type = payload.get("type")
    if token_type != expected_type:
        raise InvalidTokenError(f"Expected {expected_type} token, got {token_type}")

    return payload
