"""
Tests d'intégration — Company endpoints (CRUD complet + recherche)
"""

import pytest
from httpx import AsyncClient


# ── Fixtures ──────────────────────────────────────────────────────────────────

COMPANY_PAYLOAD = {
    "name": "NVIDIA Corporation",
    "ticker": "NVDA",
    "isin": "US67066G1040",
    "exchange": "NASDAQ",
    "company_type": "public",
    "status": "active",
    "sector": "Technology",
    "industry": "Semiconductors",
    "country": "US",
    "country_name": "United States",
    "description": "NVIDIA Corporation designs and manufactures GPUs.",
    "description_short": "Leading GPU manufacturer and AI accelerator company.",
    "website": "https://nvidia.com",
    "founded_year": 1993,
    "market_cap_usd": 3000000000,
    "employees": 29600,
    "tags": ["AI", "semiconductors", "GPU"],
}

PRIVATE_COMPANY_PAYLOAD = {
    "name": "SpaceX",
    "company_type": "private",
    "status": "active",
    "sector": "Aerospace",
    "country": "US",
    "description_short": "Space exploration company.",
    "founded_year": 2002,
}


async def make_analyst_user(client: AsyncClient) -> dict[str, str]:
    """Crée un utilisateur analyst et retourne ses headers d'auth."""
    # Enregistrement
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "analyst@atlas.io",
            "name": "Atlas Analyst",
            "password": "AnalystPass1",
        },
    )
    # Login
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "analyst@atlas.io", "password": "AnalystPass1"},
    )
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def make_admin_user(client: AsyncClient) -> dict[str, str]:
    """Crée un admin et retourne ses headers (via injection directe en DB)."""
    # Note: en test on utilise un user normal pour les endpoints analyst,
    # et on mock le rôle via le test_user fixture qui est USER par défaut.
    # Pour les tests admin, on utilise le même token mais on teste les 403.
    from app.models.user import UserRole
    return await make_analyst_user(client)


# ── Tests CRUD ────────────────────────────────────────────────────────────────

class TestCreateCompany:
    async def test_create_requires_auth(self, client: AsyncClient):
        response = await client.post("/api/v1/companies", json=COMPANY_PAYLOAD)
        assert response.status_code == 401

    async def test_create_requires_analyst_role(self, client: AsyncClient, auth_headers):
        """Un USER ne peut pas créer une entreprise."""
        response = await client.post(
            "/api/v1/companies",
            json=COMPANY_PAYLOAD,
            headers=auth_headers,
        )
        assert response.status_code == 403

    async def test_create_success(self, client: AsyncClient, analyst_headers):
        response = await client.post(
            "/api/v1/companies",
            json=COMPANY_PAYLOAD,
            headers=analyst_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "NVIDIA Corporation"
        assert data["ticker"] == "NVDA"
        assert data["isin"] == "US67066G1040"
        assert data["slug"] == "nvidia-corporation"
        assert data["country"] == "US"
        assert "id" in data
        assert "created_at" in data

    async def test_create_slug_auto_generated(self, client: AsyncClient, analyst_headers):
        response = await client.post(
            "/api/v1/companies",
            json={**COMPANY_PAYLOAD, "name": "Apple Inc", "ticker": "AAPL", "isin": None},
            headers=analyst_headers,
        )
        assert response.status_code == 201
        assert response.json()["slug"] == "apple-inc"

    async def test_create_private_company_no_ticker(self, client: AsyncClient, analyst_headers):
        response = await client.post(
            "/api/v1/companies",
            json=PRIVATE_COMPANY_PAYLOAD,
            headers=analyst_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["company_type"] == "private"
        assert data["ticker"] is None

    async def test_create_duplicate_ticker_fails(self, client: AsyncClient, analyst_headers, created_company):
        response = await client.post(
            "/api/v1/companies",
            json={**COMPANY_PAYLOAD, "name": "Other Company", "isin": None},
            headers=analyst_headers,
        )
        assert response.status_code == 409

    async def test_create_duplicate_isin_fails(self, client: AsyncClient, analyst_headers, created_company):
        response = await client.post(
            "/api/v1/companies",
            json={**COMPANY_PAYLOAD, "name": "Other Company", "ticker": "OTHER"},
            headers=analyst_headers,
        )
        assert response.status_code == 409

    async def test_create_invalid_isin_format(self, client: AsyncClient, analyst_headers):
        response = await client.post(
            "/api/v1/companies",
            json={**COMPANY_PAYLOAD, "ticker": "XYZ", "isin": "INVALID"},
            headers=analyst_headers,
        )
        assert response.status_code == 422

    async def test_create_missing_required_country(self, client: AsyncClient, analyst_headers):
        payload = {k: v for k, v in COMPANY_PAYLOAD.items() if k != "country"}
        response = await client.post(
            "/api/v1/companies",
            json=payload,
            headers=analyst_headers,
        )
        assert response.status_code == 422


class TestGetCompany:
    async def test_get_by_id(self, client: AsyncClient, created_company):
        company_id = created_company["id"]
        response = await client.get(f"/api/v1/companies/{company_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == company_id
        assert data["name"] == "NVIDIA Corporation"

    async def test_get_by_slug(self, client: AsyncClient, created_company):
        response = await client.get("/api/v1/companies/by-slug/nvidia-corporation")
        assert response.status_code == 200
        assert response.json()["name"] == "NVIDIA Corporation"

    async def test_get_by_ticker(self, client: AsyncClient, created_company):
        response = await client.get("/api/v1/companies/by-ticker/NVDA")
        assert response.status_code == 200
        assert response.json()["ticker"] == "NVDA"

    async def test_get_by_ticker_case_insensitive(self, client: AsyncClient, created_company):
        response = await client.get("/api/v1/companies/by-ticker/nvda")
        assert response.status_code == 200
        assert response.json()["ticker"] == "NVDA"

    async def test_get_nonexistent_returns_404(self, client: AsyncClient):
        import uuid
        response = await client.get(f"/api/v1/companies/{uuid.uuid4()}")
        assert response.status_code == 404

    async def test_get_nonexistent_slug_returns_404(self, client: AsyncClient):
        response = await client.get("/api/v1/companies/by-slug/does-not-exist")
        assert response.status_code == 404

    async def test_get_nonexistent_ticker_returns_404(self, client: AsyncClient):
        response = await client.get("/api/v1/companies/by-ticker/XXXXX")
        assert response.status_code == 404

    async def test_get_no_auth_required(self, client: AsyncClient, created_company):
        """La lecture est publique — pas d'authentification requise."""
        company_id = created_company["id"]
        response = await client.get(f"/api/v1/companies/{company_id}")
        assert response.status_code == 200


class TestListCompanies:
    async def test_list_returns_paginated(self, client: AsyncClient, created_company):
        response = await client.get("/api/v1/companies")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert isinstance(data["items"], list)

    async def test_list_no_auth_required(self, client: AsyncClient):
        response = await client.get("/api/v1/companies")
        assert response.status_code == 200

    async def test_search_by_name(self, client: AsyncClient, created_company):
        response = await client.get("/api/v1/companies?q=NVIDIA")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        names = [item["name"] for item in data["items"]]
        assert any("NVIDIA" in n for n in names)

    async def test_search_case_insensitive(self, client: AsyncClient, created_company):
        response = await client.get("/api/v1/companies?q=nvidia")
        assert response.status_code == 200
        assert response.json()["total"] >= 1

    async def test_filter_by_sector(self, client: AsyncClient, created_company):
        response = await client.get("/api/v1/companies?sector=Technology")
        assert response.status_code == 200
        items = response.json()["items"]
        if items:
            assert all(item["sector"] == "Technology" for item in items)

    async def test_filter_by_country(self, client: AsyncClient, created_company):
        response = await client.get("/api/v1/companies?country=US")
        assert response.status_code == 200
        items = response.json()["items"]
        if items:
            assert all(item["country"] == "US" for item in items)

    async def test_filter_by_company_type(self, client: AsyncClient, created_company):
        response = await client.get("/api/v1/companies?company_type=public")
        assert response.status_code == 200

    async def test_pagination_page_2(self, client: AsyncClient, created_company):
        response = await client.get("/api/v1/companies?page=2&page_size=1")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2

    async def test_empty_search_returns_no_results(self, client: AsyncClient):
        response = await client.get("/api/v1/companies?q=xyznotexistingcompany123")
        assert response.status_code == 200
        assert response.json()["total"] == 0


class TestUpdateCompany:
    async def test_update_requires_auth(self, client: AsyncClient, created_company):
        company_id = created_company["id"]
        response = await client.patch(
            f"/api/v1/companies/{company_id}",
            json={"sector": "AI"},
        )
        assert response.status_code == 401

    async def test_update_success(self, client: AsyncClient, created_company, analyst_headers):
        company_id = created_company["id"]
        response = await client.patch(
            f"/api/v1/companies/{company_id}",
            json={"sector": "AI & Semiconductors", "employees": 30000},
            headers=analyst_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["sector"] == "AI & Semiconductors"
        assert data["employees"] == 30000
        # Les autres champs ne changent pas
        assert data["name"] == "NVIDIA Corporation"

    async def test_update_nonexistent_returns_404(self, client: AsyncClient, analyst_headers):
        import uuid
        response = await client.patch(
            f"/api/v1/companies/{uuid.uuid4()}",
            json={"sector": "Technology"},
            headers=analyst_headers,
        )
        assert response.status_code == 404

    async def test_update_empty_body_returns_unchanged(
        self, client: AsyncClient, created_company, analyst_headers
    ):
        """Un PATCH avec un corps vide retourne l'entreprise inchangée."""
        company_id = created_company["id"]
        response = await client.patch(
            f"/api/v1/companies/{company_id}",
            json={},
            headers=analyst_headers,
        )
        assert response.status_code == 200
        assert response.json()["name"] == "NVIDIA Corporation"


class TestDeleteCompany:
    async def test_delete_requires_auth(self, client: AsyncClient, created_company):
        company_id = created_company["id"]
        response = await client.delete(f"/api/v1/companies/{company_id}")
        assert response.status_code == 401

    async def test_delete_requires_admin(self, client: AsyncClient, created_company, analyst_headers):
        """Un analyst ne peut pas supprimer."""
        company_id = created_company["id"]
        response = await client.delete(
            f"/api/v1/companies/{company_id}",
            headers=analyst_headers,
        )
        assert response.status_code == 403

    async def test_soft_delete_success(
        self, client: AsyncClient, created_company, admin_headers
    ):
        company_id = created_company["id"]
        response = await client.delete(
            f"/api/v1/companies/{company_id}",
            headers=admin_headers,
        )
        assert response.status_code == 204

    async def test_deleted_company_not_found(
        self, client: AsyncClient, created_company, admin_headers
    ):
        """Après soft delete, l'entreprise n'est plus accessible via l'API."""
        company_id = created_company["id"]
        await client.delete(f"/api/v1/companies/{company_id}", headers=admin_headers)
        response = await client.get(f"/api/v1/companies/{company_id}")
        assert response.status_code == 404


class TestSpecialEndpoints:
    async def test_get_sectors(self, client: AsyncClient, created_company):
        response = await client.get("/api/v1/companies/sectors")
        assert response.status_code == 200
        sectors = response.json()
        assert isinstance(sectors, list)
        assert "Technology" in sectors

    async def test_get_countries(self, client: AsyncClient, created_company):
        response = await client.get("/api/v1/companies/countries")
        assert response.status_code == 200
        countries = response.json()
        assert "US" in countries

    async def test_get_featured_empty(self, client: AsyncClient):
        response = await client.get("/api/v1/companies/featured")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
