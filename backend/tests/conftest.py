"""
Atlas - Test Configuration
===========================
Configuration pytest avec base de données de test isolée.

Stratégie de test :
- Base PostgreSQL de test dédiée (atlas_test)
- Chaque test s'exécute dans une transaction rollbackée → isolation totale
- Pas de mocking de la DB — on teste contre une vraie DB pour plus de fiabilité
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.database import Base, get_db_session
from app.main import create_app
from app.models.user import User, UserRole
from app.core.security import hash_password


# URL de la DB de test
TEST_DATABASE_URL = "postgresql+asyncpg://atlas:atlas@localhost:5432/atlas_test"


@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.DefaultEventLoopPolicy()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Moteur de test créé une seule fois pour toute la session."""
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Session de test isolée via une transaction rollbackée.
    Chaque test repart d'un état propre sans recréer les tables.
    """
    connection = await test_engine.connect()
    transaction = await connection.begin()

    session_factory = async_sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with session_factory() as session:
        yield session

    await transaction.rollback()
    await connection.close()


@pytest_asyncio.fixture
async def app(db_session: AsyncSession) -> FastAPI:
    """Application FastAPI avec la DB de test injectée."""
    application = create_app()

    async def override_get_db():
        yield db_session

    application.dependency_overrides[get_db_session] = override_get_db
    return application


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Client HTTP pour les tests d'intégration."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Crée un utilisateur de test (rôle USER) dans la DB."""
    from app.repositories.user import UserRepository

    repo = UserRepository(db_session)
    user = await repo.create(
        email="test@atlas.io",
        name="Test User",
        hashed_password=hash_password("TestPassword1"),
        auth_provider="local",
    )
    return user


@pytest_asyncio.fixture
async def analyst_user(db_session: AsyncSession) -> User:
    """Crée un utilisateur avec le rôle ANALYST."""
    from app.repositories.user import UserRepository

    repo = UserRepository(db_session)
    user = await repo.create(
        email="analyst@atlas.io",
        name="Atlas Analyst",
        hashed_password=hash_password("AnalystPass1"),
        auth_provider="local",
        role=UserRole.ANALYST,
    )
    return user


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Crée un utilisateur avec le rôle ADMIN."""
    from app.repositories.user import UserRepository

    repo = UserRepository(db_session)
    user = await repo.create(
        email="admin@atlas.io",
        name="Atlas Admin",
        hashed_password=hash_password("AdminPass1"),
        auth_provider="local",
        role=UserRole.ADMIN,
    )
    return user


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, test_user: User) -> dict[str, str]:
    """Retourne les headers d'authentification pour un USER (rôle minimal)."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@atlas.io", "password": "TestPassword1"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def analyst_headers(client: AsyncClient, analyst_user: User) -> dict[str, str]:
    """Retourne les headers d'authentification pour un ANALYST."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "analyst@atlas.io", "password": "AnalystPass1"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def admin_headers(client: AsyncClient, admin_user: User) -> dict[str, str]:
    """Retourne les headers d'authentification pour un ADMIN."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@atlas.io", "password": "AdminPass1"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def created_company(client: AsyncClient, analyst_headers: dict) -> dict:
    """Crée une entreprise de test et retourne sa représentation JSON."""
    response = await client.post(
        "/api/v1/companies",
        json={
            "name": "NVIDIA Corporation",
            "ticker": "NVDA",
            "isin": "US67066G1040",
            "exchange": "NASDAQ",
            "company_type": "public",
            "status": "active",
            "sector": "Technology",
            "industry": "Semiconductors",
            "country": "US",
            "description_short": "Leading GPU manufacturer.",
            "website": "https://nvidia.com",
            "founded_year": 1993,
            "market_cap_usd": 3000000000,
            "employees": 29600,
            "tags": ["AI", "semiconductors"],
        },
        headers=analyst_headers,
    )
    assert response.status_code == 201
    return response.json()


@pytest_asyncio.fixture
async def created_theme(client: AsyncClient, analyst_headers: dict) -> dict:
    """Crée un thème de test et retourne sa représentation JSON."""
    response = await client.post(
        "/api/v1/themes",
        json={
            "name": "Artificial Intelligence",
            "description": "AI and machine learning companies.",
            "category": "Technology",
            "maturity_level": "growth",
            "color": "#6366f1",
            "icon": "cpu",
            "is_active": True,
        },
        headers=analyst_headers,
    )
    assert response.status_code == 201
    return response.json()


@pytest_asyncio.fixture
async def created_event(
    client: AsyncClient, created_company: dict, analyst_headers: dict
) -> dict:
    """Crée un event de test lié à created_company."""
    response = await client.post(
        "/api/v1/events",
        json={
            "company_id": created_company["id"],
            "event_type": "funding",
            "importance": "high",
            "title": "Series B — $50M raised",
            "summary": "Company raises $50M.",
            "occurred_at": "2025-01-15T10:00:00Z",
            "source": "crunchbase",
            "source_id": "cb_test_fixture_001",
            "confidence_score": 0.95,
        },
        headers=analyst_headers,
    )
    assert response.status_code == 201
    return response.json()


@pytest_asyncio.fixture
async def created_relation(
    client: AsyncClient, created_company: dict, created_theme: dict, analyst_headers: dict
) -> dict:
    """Crée une relation de test entre une company et un theme."""
    response = await client.post(
        "/api/v1/graph/relations",
        json={
            "source_type": "company",
            "source_id": created_company["id"],
            "target_type": "theme",
            "target_id": created_theme["id"],
            "relation_type": "member_of_theme",
            "weight": 0.9,
            "confidence_score": 1.0,
            "source_label": "NVIDIA Corporation",
            "target_label": "Artificial Intelligence",
        },
        headers=analyst_headers,
    )
    assert response.status_code == 201
    return response.json()
