"""
Tests d'intégration — Endpoints d'authentification
"""

import pytest
from httpx import AsyncClient


class TestRegister:
    async def test_register_success(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@atlas.io",
                "name": "New User",
                "password": "SecurePass1",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@atlas.io"
        assert data["name"] == "New User"
        assert "hashed_password" not in data
        assert "password" not in data
        assert "id" in data

    async def test_register_duplicate_email(self, client: AsyncClient, test_user):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@atlas.io",  # Already exists via test_user fixture
                "name": "Duplicate",
                "password": "SecurePass1",
            },
        )
        assert response.status_code == 409
        assert "error" in response.json()

    async def test_register_weak_password(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "weak@atlas.io",
                "name": "Weak User",
                "password": "weakpass",  # No uppercase, no digit
            },
        )
        assert response.status_code == 422

    async def test_register_invalid_email(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "name": "Test",
                "password": "SecurePass1",
            },
        )
        assert response.status_code == 422


class TestLogin:
    async def test_login_success(self, client: AsyncClient, test_user):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@atlas.io", "password": "TestPassword1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient, test_user):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@atlas.io", "password": "WrongPassword1"},
        )
        assert response.status_code == 401

    async def test_login_unknown_email(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@atlas.io", "password": "SomePassword1"},
        )
        assert response.status_code == 401

    async def test_login_response_has_no_sensitive_data(self, client: AsyncClient, test_user):
        """Le token ne doit pas contenir de données sensibles en clair."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@atlas.io", "password": "TestPassword1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "password" not in data
        assert "hashed_password" not in data


class TestRefreshToken:
    async def test_refresh_success(self, client: AsyncClient, test_user):
        # D'abord on se connecte
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@atlas.io", "password": "TestPassword1"},
        )
        refresh_token = login_response.json()["refresh_token"]

        # Puis on rafraîchit
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_refresh_with_access_token_fails(self, client: AsyncClient, test_user):
        """On ne peut pas utiliser un access token comme refresh token."""
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@atlas.io", "password": "TestPassword1"},
        )
        access_token = login_response.json()["access_token"]

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token},
        )
        assert response.status_code == 401


class TestGetMe:
    async def test_get_me_authenticated(self, client: AsyncClient, auth_headers):
        response = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@atlas.io"
        assert "hashed_password" not in data

    async def test_get_me_unauthenticated(self, client: AsyncClient):
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    async def test_get_me_invalid_token(self, client: AsyncClient):
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert response.status_code == 401


class TestHealthEndpoints:
    async def test_health_returns_200(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "uptime_seconds" in data

    async def test_request_id_in_response_headers(self, client: AsyncClient):
        """Chaque réponse doit inclure un X-Request-ID."""
        response = await client.get("/health")
        assert "x-request-id" in response.headers
        assert len(response.headers["x-request-id"]) == 36  # UUID v4
