"""Tests d'intégration — Event endpoints"""

import pytest
from datetime import UTC, datetime
from httpx import AsyncClient


EVENT_PAYLOAD = {
    "event_type": "funding",
    "importance": "high",
    "title": "Series B — $50M raised",
    "summary": "Company raises $50M to expand globally.",
    "occurred_at": "2025-01-15T10:00:00Z",
    "source": "crunchbase",
    "source_url": "https://crunchbase.com/funding/123",
    "source_id": "cb_funding_123",
    "confidence_score": 0.95,
}


class TestCreateEvent:
    async def test_create_requires_auth(self, client: AsyncClient, created_company):
        payload = {**EVENT_PAYLOAD, "company_id": created_company["id"]}
        r = await client.post("/api/v1/events", json=payload)
        assert r.status_code == 401

    async def test_create_success(self, client: AsyncClient, created_company, analyst_headers):
        payload = {**EVENT_PAYLOAD, "company_id": created_company["id"]}
        r = await client.post("/api/v1/events", json=payload, headers=analyst_headers)
        assert r.status_code == 201
        data = r.json()
        assert data["event_type"] == "funding"
        assert data["importance"] == "high"
        assert data["confidence_score"] == 0.95
        assert data["is_processed"] is False
        assert "score_boost" in data
        assert data["score_boost"] > 0

    async def test_create_nonexistent_company_404(self, client: AsyncClient, analyst_headers):
        import uuid
        payload = {**EVENT_PAYLOAD, "company_id": str(uuid.uuid4())}
        r = await client.post("/api/v1/events", json=payload, headers=analyst_headers)
        assert r.status_code == 404

    async def test_create_duplicate_source_id_fails(
        self, client: AsyncClient, created_company, analyst_headers
    ):
        payload = {**EVENT_PAYLOAD, "company_id": created_company["id"]}
        await client.post("/api/v1/events", json=payload, headers=analyst_headers)
        r = await client.post("/api/v1/events", json=payload, headers=analyst_headers)
        assert r.status_code == 409

    async def test_create_no_source_id_allowed_twice(
        self, client: AsyncClient, created_company, analyst_headers
    ):
        """Sans source_id, deux events identiques peuvent coexister."""
        payload = {**EVENT_PAYLOAD, "company_id": created_company["id"], "source_id": None}
        r1 = await client.post("/api/v1/events", json=payload, headers=analyst_headers)
        r2 = await client.post("/api/v1/events", json=payload, headers=analyst_headers)
        assert r1.status_code == 201
        assert r2.status_code == 201

    async def test_score_boost_negative_for_fda_rejection(
        self, client: AsyncClient, created_company, analyst_headers
    ):
        payload = {
            **EVENT_PAYLOAD,
            "company_id": created_company["id"],
            "event_type": "fda_rejection",
            "source_id": "fda_rej_001",
        }
        r = await client.post("/api/v1/events", json=payload, headers=analyst_headers)
        assert r.status_code == 201
        assert r.json()["score_boost"] < 0


class TestGetEvent:
    async def test_get_by_id(self, client: AsyncClient, created_event):
        r = await client.get(f"/api/v1/events/{created_event['id']}")
        assert r.status_code == 200
        assert r.json()["id"] == created_event["id"]

    async def test_get_nonexistent_404(self, client: AsyncClient):
        import uuid
        r = await client.get(f"/api/v1/events/{uuid.uuid4()}")
        assert r.status_code == 404

    async def test_get_no_auth_required(self, client: AsyncClient, created_event):
        r = await client.get(f"/api/v1/events/{created_event['id']}")
        assert r.status_code == 200


class TestListEvents:
    async def test_list_returns_paginated(self, client: AsyncClient, created_event):
        r = await client.get("/api/v1/events")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data and "total" in data

    async def test_filter_by_company(self, client: AsyncClient, created_event, created_company):
        r = await client.get(f"/api/v1/events?company_id={created_company['id']}")
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    async def test_filter_by_type(self, client: AsyncClient, created_event):
        r = await client.get("/api/v1/events?event_type=funding")
        assert r.status_code == 200
        items = r.json()["items"]
        assert all(i["event_type"] == "funding" for i in items)

    async def test_filter_by_importance(self, client: AsyncClient, created_event):
        r = await client.get("/api/v1/events?importance=high")
        assert r.status_code == 200

    async def test_filter_unprocessed(self, client: AsyncClient, created_event):
        r = await client.get("/api/v1/events?is_processed=false")
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    async def test_types_endpoint(self, client: AsyncClient):
        r = await client.get("/api/v1/events/types")
        assert r.status_code == 200
        types = r.json()
        assert isinstance(types, list)
        assert len(types) > 0
        assert all("type" in t and "score_boost" in t for t in types)
        # FDA rejection doit être négatif
        fda_rej = next(t for t in types if t["type"] == "fda_rejection")
        assert fda_rej["score_boost"] < 0


class TestUpdateEvent:
    async def test_update_success(self, client: AsyncClient, created_event, analyst_headers):
        r = await client.patch(
            f"/api/v1/events/{created_event['id']}",
            json={"importance": "critical", "sentiment_score": 0.8},
            headers=analyst_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["importance"] == "critical"
        assert data["sentiment_score"] == 0.8

    async def test_update_requires_auth(self, client: AsyncClient, created_event):
        r = await client.patch(
            f"/api/v1/events/{created_event['id']}",
            json={"importance": "critical"},
        )
        assert r.status_code == 401


class TestDeleteEvent:
    async def test_delete_requires_admin(self, client: AsyncClient, created_event, analyst_headers):
        r = await client.delete(
            f"/api/v1/events/{created_event['id']}", headers=analyst_headers
        )
        assert r.status_code == 403

    async def test_delete_success(self, client: AsyncClient, created_event, admin_headers):
        r = await client.delete(
            f"/api/v1/events/{created_event['id']}", headers=admin_headers
        )
        assert r.status_code == 204

    async def test_deleted_event_not_found(
        self, client: AsyncClient, created_event, admin_headers
    ):
        await client.delete(f"/api/v1/events/{created_event['id']}", headers=admin_headers)
        r = await client.get(f"/api/v1/events/{created_event['id']}")
        assert r.status_code == 404


class TestCompanyEvents:
    async def test_company_events_list(
        self, client: AsyncClient, created_company, created_event
    ):
        r = await client.get(f"/api/v1/companies/{created_company['id']}/events")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1

    async def test_company_events_stats(
        self, client: AsyncClient, created_company, created_event
    ):
        r = await client.get(f"/api/v1/companies/{created_company['id']}/events/stats")
        assert r.status_code == 200
        data = r.json()
        assert data["company_id"] == created_company["id"]
        assert data["total_events"] >= 1
        assert "by_type" in data
        assert "by_importance" in data
        assert "estimated_score_boost" in data

    async def test_company_events_nonexistent_company(self, client: AsyncClient):
        import uuid
        r = await client.get(f"/api/v1/companies/{uuid.uuid4()}/events")
        assert r.status_code == 404
