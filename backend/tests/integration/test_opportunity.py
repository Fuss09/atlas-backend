"""Tests d'intégration — Opportunity endpoints"""

from httpx import AsyncClient


class TestGetOpportunity:
    async def test_get_computes_on_first_request(
        self, client: AsyncClient, created_company: dict
    ):
        """Aucun score n'existe encore — il doit être calculé à la volée."""
        r = await client.get(f"/api/v1/companies/{created_company['id']}/opportunity")
        assert r.status_code == 200
        data = r.json()
        assert 0 <= data["score"] <= 100
        assert data["conviction"] in ("low", "moderate", "high", "very_high")
        assert data["stage"] in ("early", "acceleration", "confirmation", "mature")
        assert "market_signals" in data["components"]
        assert data["components"]["market_signals"]["value"] is None
        assert data["components"]["market_signals"]["is_connected"] is False
        assert isinstance(data["positive_factors"], list)
        assert isinstance(data["negative_factors"], list)

    async def test_get_nonexistent_company_404(self, client: AsyncClient):
        import uuid

        r = await client.get(f"/api/v1/companies/{uuid.uuid4()}/opportunity")
        assert r.status_code == 404

    async def test_get_is_idempotent_without_new_events(
        self, client: AsyncClient, created_company: dict
    ):
        r1 = await client.get(f"/api/v1/companies/{created_company['id']}/opportunity")
        r2 = await client.get(f"/api/v1/companies/{created_company['id']}/opportunity")
        assert r1.json()["score"] == r2.json()["score"]
        assert r1.json()["id"] == r2.json()["id"]


class TestRecomputeOpportunity:
    async def test_recompute_requires_auth(self, client: AsyncClient, created_company: dict):
        r = await client.post(
            f"/api/v1/companies/{created_company['id']}/opportunity/recompute"
        )
        assert r.status_code == 401

    async def test_recompute_reflects_new_events(
        self, client: AsyncClient, created_company: dict, analyst_headers: dict
    ):
        before = await client.get(f"/api/v1/companies/{created_company['id']}/opportunity")
        before_score = before.json()["score"]

        await client.post(
            "/api/v1/events",
            json={
                "company_id": created_company["id"],
                "event_type": "fda_approval",
                "importance": "critical",
                "title": "FDA approval granted",
                "occurred_at": "2026-07-01T00:00:00Z",
                "source": "fda",
                "source_id": "fda_test_001",
                "confidence_score": 1.0,
            },
            headers=analyst_headers,
        )

        after = await client.post(
            f"/api/v1/companies/{created_company['id']}/opportunity/recompute",
            headers=analyst_headers,
        )
        assert after.status_code == 200
        assert after.json()["score"] >= before_score
        assert any(
            "Fda Approval" in f for f in after.json()["positive_factors"]
        )

    async def test_recompute_updates_company_atlas_score(
        self, client: AsyncClient, created_company: dict, analyst_headers: dict
    ):
        result = await client.post(
            f"/api/v1/companies/{created_company['id']}/opportunity/recompute",
            headers=analyst_headers,
        )
        score = result.json()["score"]

        company = await client.get(f"/api/v1/companies/{created_company['id']}")
        assert company.json()["atlas_score"] == score


class TestListOpportunities:
    async def test_list_returns_paginated_results(
        self, client: AsyncClient, created_company: dict
    ):
        await client.get(f"/api/v1/companies/{created_company['id']}/opportunity")
        r = await client.get("/api/v1/opportunities")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert data["total"] >= 1

    async def test_list_sorted_by_score_desc(
        self, client: AsyncClient, created_company: dict
    ):
        await client.get(f"/api/v1/companies/{created_company['id']}/opportunity")
        r = await client.get("/api/v1/opportunities")
        scores = [item["score"] for item in r.json()["items"]]
        assert scores == sorted(scores, reverse=True)

    async def test_list_filters_by_min_score(
        self, client: AsyncClient, created_company: dict
    ):
        await client.get(f"/api/v1/companies/{created_company['id']}/opportunity")
        r = await client.get("/api/v1/opportunities", params={"min_score": 101})
        assert r.json()["total"] == 0
