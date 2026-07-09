"""
Atlas - Core Configuration
==========================
Centralise toute la configuration de l'application via des variables d'environnement.
Utilise Pydantic Settings v2 pour la validation et le typage fort.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Configuration PostgreSQL."""

    model_config = SettingsConfigDict(env_prefix="POSTGRES_")

    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    user: str = Field(default="atlas")
    password: str = Field(default="atlas")
    db: str = Field(default="atlas")
    pool_size: int = Field(default=10)
    max_overflow: int = Field(default=20)
    pool_timeout: int = Field(default=30)
    echo: bool = Field(default=False)

    @property
    def url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"

    @property
    def sync_url(self) -> str:
        """Used only for Alembic migrations (sync driver)."""
        return f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


class RedisSettings(BaseSettings):
    """Configuration Redis."""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    password: str | None = Field(default=None)
    db: int = Field(default=0)
    max_connections: int = Field(default=20)

    @property
    def url(self) -> str:
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class RabbitMQSettings(BaseSettings):
    """Configuration RabbitMQ."""

    model_config = SettingsConfigDict(env_prefix="RABBITMQ_")

    host: str = Field(default="localhost")
    port: int = Field(default=5672)
    user: str = Field(default="atlas")
    password: str = Field(default="atlas")
    vhost: str = Field(default="/")

    @property
    def url(self) -> str:
        return f"amqp://{self.user}:{self.password}@{self.host}:{self.port}/{self.vhost}"


class Neo4jSettings(BaseSettings):
    """Configuration Neo4j."""

    model_config = SettingsConfigDict(env_prefix="NEO4J_")

    uri: str = Field(default="bolt://localhost:7687")
    user: str = Field(default="neo4j")
    password: str = Field(default="atlas_neo4j")


class JWTSettings(BaseSettings):
    """Configuration JWT."""

    model_config = SettingsConfigDict(env_prefix="JWT_")

    secret_key: str = Field(default="CHANGE_THIS_IN_PRODUCTION_PLEASE")
    algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30)
    refresh_token_expire_days: int = Field(default=30)

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT secret key must be at least 32 characters long")
        return v


class Settings(BaseSettings):
    """
    Configuration principale d'Atlas.
    Toutes les variables d'environnement sont validées au démarrage.
    Si une variable critique est manquante, l'application ne démarre pas.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="Atlas Market Intelligence")
    app_version: str = Field(default="0.1.0")
    environment: Literal["development", "staging", "production"] = Field(default="development")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    # API
    api_prefix: str = Field(default="/api/v1")
    allowed_origins: list[str] = Field(default=["http://localhost:3000"])

    # Services config
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    rabbitmq: RabbitMQSettings = Field(default_factory=RabbitMQSettings)
    neo4j: Neo4jSettings = Field(default_factory=Neo4jSettings)
    jwt: JWTSettings = Field(default_factory=JWTSettings)

    # Feature flags — utiles pendant le développement progressif
    feature_neo4j_enabled: bool = Field(default=True)
    feature_rabbitmq_enabled: bool = Field(default=True)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Retourne l'instance unique des settings.
    Le cache LRU garantit qu'une seule instance est créée pour toute l'application.
    En tests, appeler get_settings.cache_clear() pour réinitialiser.
    """
    return Settings()
