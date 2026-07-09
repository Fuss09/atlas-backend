"""Tests d'intégration — Discovery endpoints"""

import pytest
from httpx import AsyncClient


class TestDiscoverySources:
    async def test_get_sources_public(self, client: AsyncClient):
        r = await client.get("/api/v1/discovery/sources")
        assert r.status_code == 200
        sources = r.json()
        assert isinstance(sources, list)
        names = [s["source"] for s in sources]
        assert "sec" in names
        assert "github" in names
        assert "ycombinator" in names
        assert "crunchbase" in names
        assert "fda" in names

    async def test_sources_show_implementation_status(self, client: AsyncClient):
        r = await client.get("/api/v1/discovery/sources")
        sources = {s["source"]: s for s in r.json()}
        assert sources["sec"]["implemented"] is True
        assert sources["fda"]["implemented"] is False


class TestDiscoveryJobs:
    async def test_list_jobs_requires_auth(self, client: AsyncClient):
        r = await client.get("/api/v1/discovery/jobs")
        assert r.status_code == 401

    async def test_list_jobs_requires_analyst(self, client: AsyncClient, auth_headers):
        r = await client.get("/api/v1/discovery/jobs", headers=auth_headers)
        assert r.status_code == 403

    async def test_list_jobs_analyst_ok(self, client: AsyncClient, analyst_headers):
        r = await client.get("/api/v1/discovery/jobs", headers=analyst_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_trigger_job_requires_analyst(self, client: AsyncClient, auth_headers):
        r = await client.post(
            "/api/v1/discovery/jobs",
            json={"source": "sec", "params": {"limit": 5}},
            headers=auth_headers,
        )
        assert r.status_code == 403

    async def test_trigger_job_returns_202(self, client: AsyncClient, analyst_headers):
        r = await client.post(
            "/api/v1/discovery/jobs",
            json={"source": "sec", "params": {"limit": 5}},
            headers=analyst_headers,
        )
        assert r.status_code == 202
        data = r.json()
        assert data["source"] == "sec"
        assert data["status"] in ("pending", "running")
        assert "id" in data

    async def test_trigger_invalid_source(self, client: AsyncClient, analyst_headers):
        r = await client.post(
            "/api/v1/discovery/jobs",
            json={"source": "invalid_source"},
            headers=analyst_headers,
        )
        assert r.status_code == 422

    async def test_get_job_by_id(self, client: AsyncClient, analyst_headers):
        # Créer un job
        create_r = await client.post(
            "/api/v1/discovery/jobs",
            json={"source": "crunchbase", "params": {}},
            headers=analyst_headers,
        )
        assert create_r.status_code == 202
        job_id = create_r.json()["id"]

        # Récupérer le job
        r = await client.get(f"/api/v1/discovery/jobs/{job_id}", headers=analyst_headers)
        assert r.status_code == 200
        assert r.json()["id"] == job_id

    async def test_get_nonexistent_job_404(self, client: AsyncClient, analyst_headers):
        import uuid
        r = await client.get(
            f"/api/v1/discovery/jobs/{uuid.uuid4()}",
            headers=analyst_headers,
        )
        assert r.status_code == 404

    async def test_run_sync_requires_admin(self, client: AsyncClient, analyst_headers):
        r = await client.post(
            "/api/v1/discovery/jobs/run-sync",
            json={"source": "crunchbase", "params": {}},
            headers=analyst_headers,
        )
        assert r.status_code == 403

    async def test_run_sync_crunchbase_stub(self, client: AsyncClient, admin_headers):
        """Le collecteur Crunchbase en mode stub doit compléter sans erreur."""
        r = await client.post(
            "/api/v1/discovery/jobs/run-sync",
            json={"source": "crunchbase", "params": {}},
            headers=admin_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] in ("success", "partial")
        assert data["companies_found"] >= 3   # 3 entreprises stub
        assert data["companies_created"] >= 0

    async def test_list_jobs_filter_by_source(self, client: AsyncClient, analyst_headers):
        r = await client.get(
            "/api/v1/discovery/jobs?source=crunchbase",
            headers=analyst_headers,
        )
        assert r.status_code == 200
        jobs = r.json()
        if jobs:
            assert all(j["source"] == "crunchbase" for j in jobs)


class TestCompanySources:
    async def test_company_sources_after_discovery(
        self, client: AsyncClient, admin_headers, analyst_headers
    ):
        """Après un run Crunchbase stub, les entreprises ont des sources tracées."""
        # Lancer le run sync
        await client.post(
            "/api/v1/discovery/jobs/run-sync",
            json={"source": "crunchbase", "params": {}},
            headers=admin_headers,
        )

        # Chercher une des entreprises créées (Anthropic)
        r = await client.get("/api/v1/companies?q=Anthropic")
        assert r.status_code == 200
        items = r.json()["items"]

        if items:
            company_id = items[0]["id"]
            sources_r = await client.get(f"/api/v1/companies/{company_id}/sources")
            assert sources_r.status_code == 200
            sources = sources_r.json()
            assert len(sources) >= 1
            assert sources[0]["source"] == "crunchbase"
