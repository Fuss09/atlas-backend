"""Tests d'intégration — Theme endpoints (CRUD + associations)"""

import pytest
from httpx import AsyncClient

THEME_PAYLOAD = {
    "name": "Artificial Intelligence",
    "description": "AI and machine learning companies.",
    "category": "Technology",
    "maturity_level": "growth",
    "color": "#6366f1",
    "icon": "cpu",
    "is_active": True,
}

COMPANY_PAYLOAD = {
    "name": "NVIDIA Corporation",
    "ticker": "NVDA",
    "company_type": "public",
    "status": "active",
    "sector": "Technology",
    "country": "US",
    "description_short": "GPU manufacturer.",
}


class TestCreateTheme:
    async def test_create_requires_auth(self, client: AsyncClient):
        r = await client.post("/api/v1/themes", json=THEME_PAYLOAD)
        assert r.status_code == 401

    async def test_create_success(self, client: AsyncClient, analyst_headers):
        r = await client.post("/api/v1/themes", json=THEME_PAYLOAD, headers=analyst_headers)
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Artificial Intelligence"
        assert data["slug"] == "artificial-intelligence"
        assert data["color"] == "#6366f1"
        assert data["maturity_level"] == "growth"
        assert data["companies_count"] == 0

    async def test_create_duplicate_name_fails(self, client: AsyncClient, analyst_headers, created_theme):
        r = await client.post("/api/v1/themes", json=THEME_PAYLOAD, headers=analyst_headers)
        assert r.status_code == 409

    async def test_create_invalid_color(self, client: AsyncClient, analyst_headers):
        r = await client.post(
            "/api/v1/themes",
            json={**THEME_PAYLOAD, "name": "Other", "color": "red"},
            headers=analyst_headers,
        )
        assert r.status_code == 422

    async def test_create_slug_auto(self, client: AsyncClient, analyst_headers):
        r = await client.post(
            "/api/v1/themes",
            json={**THEME_PAYLOAD, "name": "Quantum Computing"},
            headers=analyst_headers,
        )
        assert r.status_code == 201
        assert r.json()["slug"] == "quantum-computing"


class TestGetTheme:
    async def test_get_by_id(self, client: AsyncClient, created_theme):
        r = await client.get(f"/api/v1/themes/{created_theme['id']}")
        assert r.status_code == 200
        assert r.json()["name"] == "Artificial Intelligence"

    async def test_get_by_slug(self, client: AsyncClient, created_theme):
        r = await client.get("/api/v1/themes/by-slug/artificial-intelligence")
        assert r.status_code == 200
        assert r.json()["id"] == created_theme["id"]

    async def test_get_nonexistent_404(self, client: AsyncClient):
        import uuid
        r = await client.get(f"/api/v1/themes/{uuid.uuid4()}")
        assert r.status_code == 404

    async def test_get_no_auth_required(self, client: AsyncClient, created_theme):
        r = await client.get(f"/api/v1/themes/{created_theme['id']}")
        assert r.status_code == 200


class TestListThemes:
    async def test_list_public(self, client: AsyncClient, created_theme):
        r = await client.get("/api/v1/themes")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) >= 1

    async def test_list_has_companies_count(self, client: AsyncClient, created_theme):
        r = await client.get("/api/v1/themes")
        assert r.status_code == 200
        items = r.json()
        assert all("companies_count" in item for item in items)

    async def test_filter_by_category(self, client: AsyncClient, created_theme):
        r = await client.get("/api/v1/themes?category=Technology")
        assert r.status_code == 200
        items = r.json()
        assert all(item["category"] == "Technology" for item in items if item["category"])

    async def test_filter_by_maturity(self, client: AsyncClient, created_theme):
        r = await client.get("/api/v1/themes?maturity_level=growth")
        assert r.status_code == 200
        items = r.json()
        assert all(item["maturity_level"] == "growth" for item in items)

    async def test_categories_endpoint(self, client: AsyncClient, created_theme):
        r = await client.get("/api/v1/themes/categories")
        assert r.status_code == 200
        cats = r.json()
        assert isinstance(cats, list)
        assert "Technology" in cats


class TestUpdateTheme:
    async def test_update_success(self, client: AsyncClient, created_theme, analyst_headers):
        r = await client.patch(
            f"/api/v1/themes/{created_theme['id']}",
            json={"maturity_level": "mature", "color": "#ff0000"},
            headers=analyst_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["maturity_level"] == "mature"
        assert data["color"] == "#ff0000"
        assert data["name"] == "Artificial Intelligence"  # inchangé

    async def test_update_empty_returns_unchanged(self, client: AsyncClient, created_theme, analyst_headers):
        r = await client.patch(
            f"/api/v1/themes/{created_theme['id']}",
            json={},
            headers=analyst_headers,
        )
        assert r.status_code == 200

    async def test_update_requires_auth(self, client: AsyncClient, created_theme):
        r = await client.patch(
            f"/api/v1/themes/{created_theme['id']}",
            json={"maturity_level": "mature"},
        )
        assert r.status_code == 401


class TestDeleteTheme:
    async def test_delete_requires_admin(self, client: AsyncClient, created_theme, analyst_headers):
        r = await client.delete(
            f"/api/v1/themes/{created_theme['id']}",
            headers=analyst_headers,
        )
        assert r.status_code == 403

    async def test_delete_success(self, client: AsyncClient, created_theme, admin_headers):
        r = await client.delete(
            f"/api/v1/themes/{created_theme['id']}",
            headers=admin_headers,
        )
        assert r.status_code == 204

    async def test_deleted_theme_not_found(self, client: AsyncClient, created_theme, admin_headers):
        await client.delete(f"/api/v1/themes/{created_theme['id']}", headers=admin_headers)
        r = await client.get(f"/api/v1/themes/{created_theme['id']}")
        assert r.status_code == 404


class TestCompanyThemeAssociation:
    async def test_add_company_to_theme(
        self, client: AsyncClient, created_theme, created_company, analyst_headers
    ):
        r = await client.post(
            f"/api/v1/themes/{created_theme['id']}/companies",
            json={"company_id": created_company["id"]},
            headers=analyst_headers,
        )
        assert r.status_code == 204

    async def test_add_company_idempotent(
        self, client: AsyncClient, created_theme, created_company, analyst_headers
    ):
        """Ajouter deux fois la même association ne doit pas échouer."""
        payload = {"company_id": created_company["id"]}
        await client.post(f"/api/v1/themes/{created_theme['id']}/companies", json=payload, headers=analyst_headers)
        r = await client.post(f"/api/v1/themes/{created_theme['id']}/companies", json=payload, headers=analyst_headers)
        assert r.status_code == 204

    async def test_theme_companies_listed(
        self, client: AsyncClient, created_theme, created_company, analyst_headers
    ):
        await client.post(
            f"/api/v1/themes/{created_theme['id']}/companies",
            json={"company_id": created_company["id"]},
            headers=analyst_headers,
        )
        r = await client.get(f"/api/v1/themes/{created_theme['id']}/companies")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == created_company["id"]

    async def test_companies_count_updates(
        self, client: AsyncClient, created_theme, created_company, analyst_headers
    ):
        await client.post(
            f"/api/v1/themes/{created_theme['id']}/companies",
            json={"company_id": created_company["id"]},
            headers=analyst_headers,
        )
        r = await client.get(f"/api/v1/themes/{created_theme['id']}")
        assert r.json()["companies_count"] == 1

    async def test_remove_company_from_theme(
        self, client: AsyncClient, created_theme, created_company, analyst_headers
    ):
        await client.post(
            f"/api/v1/themes/{created_theme['id']}/companies",
            json={"company_id": created_company["id"]},
            headers=analyst_headers,
        )
        r = await client.delete(
            f"/api/v1/themes/{created_theme['id']}/companies/{created_company['id']}",
            headers=analyst_headers,
        )
        assert r.status_code == 204

    async def test_remove_nonexistent_association_404(
        self, client: AsyncClient, created_theme, created_company, analyst_headers
    ):
        r = await client.delete(
            f"/api/v1/themes/{created_theme['id']}/companies/{created_company['id']}",
            headers=analyst_headers,
        )
        assert r.status_code == 404

    async def test_get_company_themes(
        self, client: AsyncClient, created_theme, created_company, analyst_headers
    ):
        await client.post(
            f"/api/v1/themes/{created_theme['id']}/companies",
            json={"company_id": created_company["id"]},
            headers=analyst_headers,
        )
        r = await client.get(f"/api/v1/companies/{created_company['id']}/themes")
        assert r.status_code == 200
        themes = r.json()
        assert len(themes) == 1
        assert themes[0]["id"] == created_theme["id"]

    async def test_add_requires_analyst(self, client: AsyncClient, created_theme, created_company, auth_headers):
        r = await client.post(
            f"/api/v1/themes/{created_theme['id']}/companies",
            json={"company_id": created_company["id"]},
            headers=auth_headers,
        )
        assert r.status_code == 403

    async def test_add_nonexistent_company_404(self, client: AsyncClient, created_theme, analyst_headers):
        import uuid
        r = await client.post(
            f"/api/v1/themes/{created_theme['id']}/companies",
            json={"company_id": str(uuid.uuid4())},
            headers=analyst_headers,
        )
        assert r.status_code == 404
