"""
Tests unitaires — Security (JWT, password hashing)
"""

import pytest
from jose import jwt

from app.core.config import get_settings
from app.core.exceptions import InvalidTokenError, TokenExpiredError
from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_is_different_from_plain(self):
        plain = "MySecurePassword1"
        hashed = hash_password(plain)
        assert hashed != plain

    def test_verify_correct_password(self):
        plain = "MySecurePassword1"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("CorrectPassword1")
        assert verify_password("WrongPassword1", hashed) is False

    def test_same_password_produces_different_hashes(self):
        """Argon2id utilise un salt aléatoire — deux hashes du même mot de passe sont distincts."""
        plain = "MySecurePassword1"
        hash1 = hash_password(plain)
        hash2 = hash_password(plain)
        assert hash1 != hash2


class TestJWT:
    def test_create_and_decode_access_token(self):
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        token = create_access_token(user_id)
        payload = decode_token(token, TokenType.ACCESS)
        assert payload["sub"] == user_id
        assert payload["type"] == TokenType.ACCESS

    def test_create_and_decode_refresh_token(self):
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        token = create_refresh_token(user_id)
        payload = decode_token(token, TokenType.REFRESH)
        assert payload["sub"] == user_id
        assert payload["type"] == TokenType.REFRESH

    def test_access_token_rejected_as_refresh(self):
        token = create_access_token("user-id")
        with pytest.raises(InvalidTokenError):
            decode_token(token, TokenType.REFRESH)

    def test_refresh_token_rejected_as_access(self):
        token = create_refresh_token("user-id")
        with pytest.raises(InvalidTokenError):
            decode_token(token, TokenType.ACCESS)

    def test_tampered_token_rejected(self):
        token = create_access_token("user-id")
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(InvalidTokenError):
            decode_token(tampered)

    def test_expired_token_raises_correct_error(self):
        from datetime import UTC, datetime, timedelta
        from app.core.config import get_settings

        settings = get_settings()
        payload = {
            "sub": "user-id",
            "type": TokenType.ACCESS,
            "exp": datetime.now(UTC) - timedelta(minutes=1),
            "iat": datetime.now(UTC) - timedelta(minutes=31),
        }
        expired_token = jwt.encode(
            payload, settings.jwt.secret_key, algorithm=settings.jwt.algorithm
        )
        with pytest.raises(TokenExpiredError):
            decode_token(expired_token)

    def test_extra_claims_in_access_token(self):
        token = create_access_token("user-id", extra_claims={"role": "admin"})
        payload = decode_token(token)
        assert payload["role"] == "admin"
