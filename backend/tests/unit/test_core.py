"""
Tests unitaires — Exceptions, modèles de base, repositories, middleware
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import (
    AlreadyExistsError,
    AtlasError,
    AuthenticationError,
    CacheError,
    DatabaseError,
    ExternalServiceError,
    GraphDatabaseError,
    InvalidCredentialsError,
    InvalidTokenError,
    MessageBrokerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    TokenExpiredError,
    ValidationError,
)


# ─── Tests Exceptions ─────────────────────────────────────────────────────────

class TestExceptionHierarchy:
    """Vérifie que la hiérarchie d'héritage est correcte."""

    def test_atlas_error_base(self):
        e = AtlasError("test message", code="TEST_CODE", details={"key": "val"})
        assert e.message == "test message"
        assert e.code == "TEST_CODE"
        assert e.details == {"key": "val"}

    def test_atlas_error_default_code(self):
        e = AtlasError("message")
        assert e.code == "AtlasError"

    def test_atlas_error_default_details(self):
        e = AtlasError("message")
        assert e.details == {}

    def test_token_expired_is_authentication(self):
        assert issubclass(TokenExpiredError, AuthenticationError)
        assert issubclass(TokenExpiredError, AtlasError)

    def test_invalid_token_is_authentication(self):
        assert issubclass(InvalidTokenError, AuthenticationError)

    def test_invalid_credentials_is_authentication(self):
        assert issubclass(InvalidCredentialsError, AuthenticationError)

    def test_not_found_error_format(self):
        e = NotFoundError("Company", "some-uuid")
        assert e.message == "Company not found"
        assert e.details["resource"] == "Company"
        assert e.details["identifier"] == "some-uuid"

    def test_already_exists_error_format(self):
        e = AlreadyExistsError("User", "email", "test@example.com")
        assert "email" in e.message
        assert "test@example.com" in e.message
        assert e.details["field"] == "email"

    def test_external_service_error_format(self):
        e = ExternalServiceError("OpenAI", "timeout")
        assert "OpenAI" in e.message
        assert e.details["service"] == "OpenAI"

    def test_permission_denied_is_atlas_error(self):
        assert issubclass(PermissionDeniedError, AtlasError)

    def test_database_error_is_atlas_error(self):
        assert issubclass(DatabaseError, AtlasError)

    def test_rate_limit_is_atlas_error(self):
        assert issubclass(RateLimitError, AtlasError)

    def test_cache_error_is_atlas_error(self):
        assert issubclass(CacheError, AtlasError)

    def test_graph_database_error_is_atlas_error(self):
        assert issubclass(GraphDatabaseError, AtlasError)

    def test_message_broker_error_is_atlas_error(self):
        assert issubclass(MessageBrokerError, AtlasError)

    def test_validation_error_is_atlas_error(self):
        assert issubclass(ValidationError, AtlasError)

    def test_not_found_uuid_serialized(self):
        uid = uuid.uuid4()
        e = NotFoundError("User", uid)
        assert e.details["identifier"] == str(uid)


# ─── Tests SoftDelete / Base Model ────────────────────────────────────────────

class TestSoftDeleteMixin:
    """Teste le mixin de soft delete sans base de données."""

    def _make_instance(self):
        """Crée une instance minimale du mixin pour tester."""
        from app.models.base import SoftDeleteMixin

        class FakeEntity(SoftDeleteMixin):
            deleted_at = None
            is_deleted = False

        return FakeEntity()

    def test_initial_state_not_deleted(self):
        obj = self._make_instance()
        assert obj.is_deleted is False
        assert obj.deleted_at is None

    def test_soft_delete_sets_flags(self):
        obj = self._make_instance()
        before = datetime.now(UTC)
        obj.soft_delete()
        after = datetime.now(UTC)
        assert obj.is_deleted is True
        assert obj.deleted_at is not None
        assert before <= obj.deleted_at <= after

    def test_restore_clears_flags(self):
        obj = self._make_instance()
        obj.soft_delete()
        obj.restore()
        assert obj.is_deleted is False
        assert obj.deleted_at is None

    def test_soft_delete_idempotent(self):
        """Appeler soft_delete deux fois ne doit pas lever d'erreur."""
        obj = self._make_instance()
        obj.soft_delete()
        first_deleted_at = obj.deleted_at
        obj.soft_delete()
        assert obj.is_deleted is True


# ─── Tests Config ─────────────────────────────────────────────────────────────

class TestConfig:
    """Tests unitaires de la configuration."""

    def test_settings_loads_defaults(self):
        from app.core.config import get_settings
        settings = get_settings()
        assert settings.app_name == "Atlas Market Intelligence"
        assert settings.environment == "development"

    def test_database_url_format(self):
        from app.core.config import DatabaseSettings
        db = DatabaseSettings()
        assert db.url.startswith("postgresql+asyncpg://")
        assert db.sync_url.startswith("postgresql+psycopg2://")

    def test_redis_url_without_password(self):
        from app.core.config import RedisSettings
        redis = RedisSettings()
        assert redis.url.startswith("redis://")
        assert "None" not in redis.url

    def test_redis_url_with_password(self):
        from app.core.config import RedisSettings
        redis = RedisSettings()
        redis.password = "secret"
        url = redis.url
        assert "secret" in url
        assert url.startswith("redis://:")

    def test_rabbitmq_url_format(self):
        from app.core.config import RabbitMQSettings
        rmq = RabbitMQSettings()
        assert rmq.url.startswith("amqp://")

    def test_jwt_secret_key_too_short_raises(self):
        from app.core.config import JWTSettings
        with pytest.raises(Exception):
            JWTSettings(secret_key="short")

    def test_settings_is_production(self):
        from app.core.config import get_settings
        settings = get_settings()
        # En dev par défaut
        assert settings.is_production is False
        assert settings.is_development is True


# ─── Tests Middleware ──────────────────────────────────────────────────────────

class TestRequestLoggingMiddleware:
    """Tests unitaires du middleware de logging."""

    def test_excluded_paths_defined(self):
        from app.api.middleware import RequestLoggingMiddleware
        assert "/health" in RequestLoggingMiddleware.EXCLUDED_PATHS
        assert "/ready" in RequestLoggingMiddleware.EXCLUDED_PATHS
        assert "/metrics" in RequestLoggingMiddleware.EXCLUDED_PATHS


# ─── Tests Pagination ─────────────────────────────────────────────────────────

class TestPaginationParams:
    def test_default_values(self):
        from app.api.deps import PaginationParams
        p = PaginationParams()
        assert p.page == 1
        assert p.page_size == 20

    def test_offset_calculation(self):
        from app.api.deps import PaginationParams
        p = PaginationParams(page=3, page_size=10)
        assert p.offset == 20
        assert p.limit == 10

    def test_page_minimum_is_one(self):
        from app.api.deps import PaginationParams
        p = PaginationParams(page=0)
        assert p.page == 1

    def test_page_size_maximum_is_100(self):
        from app.api.deps import PaginationParams
        p = PaginationParams(page_size=999)
        assert p.page_size == 100

    def test_page_size_minimum_is_one(self):
        from app.api.deps import PaginationParams
        p = PaginationParams(page_size=0)
        assert p.page_size == 1


# ─── Tests Schemas ────────────────────────────────────────────────────────────

class TestUserSchemas:
    def test_user_create_valid(self):
        from app.schemas.user import UserCreate
        u = UserCreate(email="test@atlas.io", name="Test User", password="SecurePass1")
        assert u.email == "test@atlas.io"

    def test_user_create_email_lowercase_enforced_by_pydantic(self):
        from app.schemas.user import UserCreate
        u = UserCreate(email="TEST@ATLAS.IO", name="Test User", password="SecurePass1")
        # Pydantic EmailStr normalise en lowercase
        assert u.email == "test@atlas.io"

    def test_user_create_password_no_uppercase_fails(self):
        from app.schemas.user import UserCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(email="test@atlas.io", name="Test", password="nouppercase1")
        assert "uppercase" in str(exc_info.value).lower()

    def test_user_create_password_no_digit_fails(self):
        from app.schemas.user import UserCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(email="test@atlas.io", name="Test", password="NoDigitHere")
        assert "digit" in str(exc_info.value).lower()

    def test_user_create_password_too_short_fails(self):
        from app.schemas.user import UserCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            UserCreate(email="test@atlas.io", name="Test", password="Ab1")

    def test_user_update_all_none(self):
        from app.schemas.user import UserUpdate
        u = UserUpdate()
        assert u.model_dump(exclude_none=True) == {}

    def test_token_response_default_type(self):
        from app.schemas.user import TokenResponse
        t = TokenResponse(access_token="access", refresh_token="refresh")
        assert t.token_type == "bearer"
