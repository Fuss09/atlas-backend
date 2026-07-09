"""
Tests d'intégration — Health endpoints, exception handlers, middleware
"""

import pytest
from httpx import AsyncClient


class TestHealthLiveness:
    async def test_health_returns_200(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200

    async def test_health_response_shape(self, client: AsyncClient):
        response = await client.get("/health")
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "uptime_seconds" in data
        assert "environment" in data
        assert "timestamp" in data

    async def test_health_uptime_positive(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.json()["uptime_seconds"] >= 0

    async def test_health_available_at_api_prefix(self, client: AsyncClient):
        """Health disponible aussi sous /api/v1/health"""
        response = await client.get("/api/v1/health")
        assert response.status_code == 200


class TestMiddlewareRequestId:
    async def test_every_response_has_request_id(self, client: AsyncClient):
        response = await client.get("/health")
        assert "x-request-id" in response.headers

    async def test_request_id_is_valid_uuid(self, client: AsyncClient):
        import uuid
        response = await client.get("/health")
        request_id = response.headers["x-request-id"]
        # Ne doit pas lever d'exception
        parsed = uuid.UUID(request_id)
        assert str(parsed) == request_id

    async def test_response_time_header_present(self, client: AsyncClient):
        response = await client.get("/health")
        assert "x-response-time" in response.headers
        assert "ms" in response.headers["x-response-time"]

    async def test_different_requests_have_different_ids(self, client: AsyncClient):
        r1 = await client.get("/health")
        r2 = await client.get("/health")
        assert r1.headers["x-request-id"] != r2.headers["x-request-id"]


class TestExceptionHandlers:
    """Vérifie que les exceptions sont normalisées en JSON."""

    async def test_404_returns_normalized_error(self, client: AsyncClient):
        response = await client.get("/api/v1/nonexistent-route")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert "timestamp" in data["error"]

    async def test_401_on_protected_route_without_token(self, client: AsyncClient):
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401
        data = response.json()
        assert "error" in data

    async def test_401_with_malformed_token(self, client: AsyncClient):
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer not.a.valid.token"},
        )
        assert response.status_code == 401

    async def test_422_on_invalid_payload(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/register",
            json={"invalid": "data"},
        )
        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "ValidationError"
        assert "errors" in data["error"]["details"]

    async def test_error_response_never_contains_traceback(self, client: AsyncClient):
        """Aucune trace Python ne doit apparaître dans les réponses d'erreur."""
        response = await client.get("/api/v1/nonexistent-route")
        body = response.text
        assert "Traceback" not in body
        assert "File " not in body
        assert "line " not in body


class TestApiVersioning:
    async def test_v1_prefix_works(self, client: AsyncClient):
        """Toutes les routes sont sous /api/v1/"""
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "v1test@atlas.io", "name": "V1 Test", "password": "SecurePass1"},
        )
        # 201 ou 409 (si déjà existant) — les deux prouvent que la route existe
        assert response.status_code in (201, 409)

    async def test_route_without_prefix_returns_404(self, client: AsyncClient):
        response = await client.post(
            "/auth/register",
            json={"email": "test@atlas.io", "name": "Test", "password": "SecurePass1"},
        )
        assert response.status_code == 404
