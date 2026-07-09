"""Tests d'intégration — Knowledge Graph endpoints"""

import uuid
import pytest
from httpx import AsyncClient


class TestCreateRelation:
    async def test_create_requires_auth(self, client: AsyncClient, created_company, created_theme):
        r = await client.post("/api/v1/graph/relations", json={
            "source_type": "company", "source_id": created_company["id"],
            "target_type": "theme", "target_id": created_theme["id"],
            "relation_type": "member_of_theme",
        })
        assert r.status_code == 401

    async def test_create_success(self, client: AsyncClient, created_company, created_theme, analyst_headers):
        r = await client.post("/api/v1/graph/relations", json={
            "source_type": "company", "source_id": created_company["id"],
            "target_type": "theme", "target_id": created_theme["id"],
            "relation_type": "member_of_theme",
            "weight": 0.9, "confidence_score": 1.0,
            "source_label": "NVIDIA", "target_label": "AI",
        }, headers=analyst_headers)
        assert r.status_code == 201
        data = r.json()
        assert data["relation_type"] == "member_of_theme"
        assert data["weight"] == 0.9
        assert data["source_label"] == "NVIDIA"
        assert data["is_inferred"] is False

    async def test_create_idempotent(self, client: AsyncClient, created_company, created_theme, analyst_headers):
        """Créer deux fois la même relation met à jour, ne crée pas de doublon."""
        payload = {
            "source_type": "company", "source_id": created_company["id"],
            "target_type": "theme", "target_id": created_theme["id"],
            "relation_type": "member_of_theme", "weight": 0.5,
        }
        r1 = await client.post("/api/v1/graph/relations", json=payload, headers=analyst_headers)
        payload["weight"] = 0.9
        r2 = await client.post("/api/v1/graph/relations", json=payload, headers=analyst_headers)
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["id"] == r2.json()["id"]  # même relation, mise à jour
        assert r2.json()["weight"] == 0.9

    async def test_create_company_competes_with(self, client: AsyncClient, created_company, analyst_headers):
        target_id = str(uuid.uuid4())
        r = await client.post("/api/v1/graph/relations", json={
            "source_type": "company", "source_id": created_company["id"],
            "target_type": "company", "target_id": target_id,
            "relation_type": "competes_with",
            "weight": 0.7, "confidence_score": 0.8,
            "is_inferred": True, "relation_source": "sec",
        }, headers=analyst_headers)
        assert r.status_code == 201
        assert r.json()["is_inferred"] is True

    async def test_all_relation_types_accepted(self, client: AsyncClient, created_company, analyst_headers):
        from app.models.graph import RelationType
        target_id = str(uuid.uuid4())
        for rt in RelationType:
            r = await client.post("/api/v1/graph/relations", json={
                "source_type": "company", "source_id": created_company["id"],
                "target_type": "company", "target_id": target_id,
                "relation_type": rt.value,
            }, headers=analyst_headers)
            assert r.status_code == 201, f"Failed for {rt.value}: {r.text}"
            target_id = str(uuid.uuid4())  # nouveau UUID pour éviter unique constraint


class TestGetRelation:
    async def test_get_by_id(self, client: AsyncClient, created_relation):
        r = await client.get(f"/api/v1/graph/relations/{created_relation['id']}")
        assert r.status_code == 200
        assert r.json()["id"] == created_relation["id"]

    async def test_get_nonexistent_404(self, client: AsyncClient):
        r = await client.get(f"/api/v1/graph/relations/{uuid.uuid4()}")
        assert r.status_code == 404

    async def test_get_no_auth_required(self, client: AsyncClient, created_relation):
        r = await client.get(f"/api/v1/graph/relations/{created_relation['id']}")
        assert r.status_code == 200


class TestUpdateRelation:
    async def test_update_weight(self, client: AsyncClient, created_relation, analyst_headers):
        r = await client.patch(
            f"/api/v1/graph/relations/{created_relation['id']}",
            json={"weight": 0.3, "confidence_score": 0.6},
            headers=analyst_headers,
        )
        assert r.status_code == 200
        assert r.json()["weight"] == 0.3
        assert r.json()["confidence_score"] == 0.6

    async def test_update_requires_auth(self, client: AsyncClient, created_relation):
        r = await client.patch(
            f"/api/v1/graph/relations/{created_relation['id']}",
            json={"weight": 0.5},
        )
        assert r.status_code == 401


class TestDeleteRelation:
    async def test_delete_requires_admin(self, client: AsyncClient, created_relation, analyst_headers):
        r = await client.delete(
            f"/api/v1/graph/relations/{created_relation['id']}",
            headers=analyst_headers,
        )
        assert r.status_code == 403

    async def test_delete_success(self, client: AsyncClient, created_relation, admin_headers):
        r = await client.delete(
            f"/api/v1/graph/relations/{created_relation['id']}",
            headers=admin_headers,
        )
        assert r.status_code == 204

    async def test_deleted_not_found(self, client: AsyncClient, created_relation, admin_headers):
        await client.delete(f"/api/v1/graph/relations/{created_relation['id']}", headers=admin_headers)
        r = await client.get(f"/api/v1/graph/relations/{created_relation['id']}")
        assert r.status_code == 404


class TestCompanyGraph:
    async def test_get_company_graph(self, client: AsyncClient, created_company, created_relation):
        r = await client.get(f"/api/v1/companies/{created_company['id']}/graph")
        assert r.status_code == 200
        data = r.json()
        assert data["company_id"] == created_company["id"]
        assert "relations" in data
        assert "neighbors" in data
        assert data["relations_count"] >= 1

    async def test_company_graph_no_auth_required(self, client: AsyncClient, created_company):
        r = await client.get(f"/api/v1/companies/{created_company['id']}/graph")
        assert r.status_code == 200

    async def test_company_graph_nonexistent(self, client: AsyncClient):
        r = await client.get(f"/api/v1/companies/{uuid.uuid4()}/graph")
        assert r.status_code == 404

    async def test_add_relation_from_company(
        self, client: AsyncClient, created_company, created_theme, analyst_headers
    ):
        r = await client.post(
            f"/api/v1/companies/{created_company['id']}/graph/relations",
            json={
                "source_type": "company", "source_id": str(uuid.uuid4()),
                "target_type": "theme", "target_id": created_theme["id"],
                "relation_type": "member_of_theme",
            },
            headers=analyst_headers,
        )
        assert r.status_code == 201
        # source forcé sur la company
        assert r.json()["source_id"] == created_company["id"]


class TestGraphStats:
    async def test_stats_endpoint(self, client: AsyncClient, created_relation):
        r = await client.get("/api/v1/graph/stats")
        assert r.status_code == 200
        data = r.json()
        assert "total_relations" in data
        assert "by_type" in data
        assert "by_source" in data
        assert data["total_relations"] >= 1

    async def test_list_with_filters(self, client: AsyncClient, created_company, created_relation):
        r = await client.get(
            f"/api/v1/graph/relations?entity_type=company&entity_id={created_company['id']}"
        )
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) >= 1

    async def test_list_without_filter_returns_empty(self, client: AsyncClient):
        r = await client.get("/api/v1/graph/relations")
        assert r.status_code == 200
        assert r.json() == []
