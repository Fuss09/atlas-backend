"""
Tests unitaires — Demo dataset seed (scripts/seed_demo.py)

Ces tests valident uniquement la *structure des données* du seed
(cohérence interne, types d'enum valides, pas de référence orpheline).
Ils ne touchent jamais une base de données — voir le docstring du
script pour le comportement d'insertion réel, qui nécessite Postgres.
"""

import importlib.util
from pathlib import Path

import pytest

from app.models.company import CompanyType
from app.models.event import EventType, ImportanceLevel
from app.models.graph import RelationType


def _load_seed_module():
    """
    Importe scripts/seed_demo.py comme un module autonome, sans passer
    par le package scripts (pas de __init__.py requis) et sans exécuter
    le bloc `if __name__ == "__main__"` (déjà gardé, donc l'import seul
    est sûr — aucune connexion DB n'est ouverte tant que seed() n'est
    pas explicitement awaited).
    """
    script_path = Path(__file__).parent.parent.parent / "scripts" / "seed_demo.py"
    spec = importlib.util.spec_from_file_location("seed_demo", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def seed_module():
    return _load_seed_module()


class TestDemoCompanies:
    def test_at_least_ten_companies(self, seed_module):
        assert len(seed_module.DEMO_COMPANIES) >= 10

    def test_covers_all_four_required_domains(self, seed_module):
        """Brief Sprint 6: AI, Quantum, Biotech, Energy must all be represented."""
        all_slugs = {slug for c in seed_module.DEMO_COMPANIES for slug in c["theme_slugs"]}
        required = {"artificial-intelligence", "quantum-computing", "biotechnology", "energy-transition"}
        assert required.issubset(all_slugs)

    def test_every_company_type_is_valid_enum(self, seed_module):
        for c in seed_module.DEMO_COMPANIES:
            assert isinstance(c["company_type"], CompanyType)

    def test_no_duplicate_slugs(self, seed_module):
        slugs = [seed_module._slugify(c["name"]) for c in seed_module.DEMO_COMPANIES]
        assert len(slugs) == len(set(slugs))

    def test_public_companies_have_ticker(self, seed_module):
        for c in seed_module.DEMO_COMPANIES:
            if c["company_type"] == CompanyType.PUBLIC:
                assert c["ticker"], f"{c['name']} is PUBLIC but has no ticker"

    def test_every_company_has_at_least_one_theme(self, seed_module):
        for c in seed_module.DEMO_COMPANIES:
            assert len(c["theme_slugs"]) >= 1, c["name"]

    def test_slug_length_within_column_limit(self, seed_module):
        # Company.slug is String(300) — the generated slug must fit comfortably.
        for c in seed_module.DEMO_COMPANIES:
            assert len(seed_module._slugify(c["name"])) <= 300


class TestDemoEvents:
    def test_every_event_references_a_real_company(self, seed_module):
        company_names = {c["name"] for c in seed_module.DEMO_COMPANIES}
        for e in seed_module.DEMO_EVENTS:
            assert e["company"] in company_names, f"Unknown company: {e['company']}"

    def test_every_event_type_is_valid_enum(self, seed_module):
        for e in seed_module.DEMO_EVENTS:
            assert isinstance(e["type"], EventType)

    def test_every_importance_is_valid_enum(self, seed_module):
        for e in seed_module.DEMO_EVENTS:
            assert isinstance(e["importance"], ImportanceLevel)

    def test_confidence_score_in_valid_range(self, seed_module):
        for e in seed_module.DEMO_EVENTS:
            assert 0.0 <= e["confidence"] <= 1.0, e["title"]

    def test_days_ago_non_negative(self, seed_module):
        for e in seed_module.DEMO_EVENTS:
            assert e["days_ago"] >= 0, e["title"]

    def test_every_company_has_at_least_one_event(self, seed_module):
        """A company with zero events would show an empty Timeline and an
        under-informative Opportunity Score on first demo — every seeded
        company should have real signal to display."""
        companies_with_events = {e["company"] for e in seed_module.DEMO_EVENTS}
        company_names = {c["name"] for c in seed_module.DEMO_COMPANIES}
        assert companies_with_events == company_names

    def test_events_span_this_week_and_this_month_buckets(self, seed_module):
        """The Timeline groups events into This week / This month / Earlier
        (Sprint 5) — the seed should populate all three so a first-time
        viewer sees the grouping in action, not just one giant bucket."""
        days = [e["days_ago"] for e in seed_module.DEMO_EVENTS]
        assert any(d <= 7 for d in days), "No events in the 'This week' bucket"
        assert any(7 < d <= 30 for d in days), "No events in the 'This month' bucket"
        assert any(d > 30 for d in days), "No events in the 'Earlier' bucket"

    def test_includes_a_variety_of_event_types(self, seed_module):
        """Brief calls out Funding/SEC/FDA/GitHub/Acquisition/Partnership/
        Discovery explicitly — assert the seed actually covers that spread,
        not just a couple of repeated types."""
        types_used = {e["type"] for e in seed_module.DEMO_EVENTS}
        expected = {
            EventType.FUNDING,
            EventType.SEC_FILING,
            EventType.FDA_APPROVAL,
            EventType.GITHUB_ACTIVITY,
            EventType.ACQUISITION,
            EventType.PARTNERSHIP,
        }
        assert expected.issubset(types_used)


class TestDemoRelations:
    def test_every_relation_references_real_companies(self, seed_module):
        company_names = {c["name"] for c in seed_module.DEMO_COMPANIES}
        for r in seed_module.DEMO_RELATIONS:
            assert r["source"] in company_names, f"Unknown source: {r['source']}"
            assert r["target"] in company_names, f"Unknown target: {r['target']}"

    def test_relation_is_not_self_referencing(self, seed_module):
        for r in seed_module.DEMO_RELATIONS:
            assert r["source"] != r["target"], r

    def test_every_relation_type_is_valid_enum(self, seed_module):
        for r in seed_module.DEMO_RELATIONS:
            assert isinstance(r["type"], RelationType)

    def test_weight_and_confidence_in_valid_range(self, seed_module):
        for r in seed_module.DEMO_RELATIONS:
            assert 0.0 <= r["weight"] <= 1.0, r
            assert 0.0 <= r["confidence"] <= 1.0, r

    def test_graph_has_at_least_one_relation_per_domain_cluster(self, seed_module):
        """Every domain (AI, Quantum, Biotech, Energy) should have at least
        one internal relation, so opening the graph from any seeded
        company shows real connected structure — not an isolated node."""
        connected_companies = set()
        for r in seed_module.DEMO_RELATIONS:
            connected_companies.add(r["source"])
            connected_companies.add(r["target"])

        by_domain = {
            "ai": {"Nexora AI", "Verdant Robotics Labs", "Halcyon Semantics"},
            "quantum": {"Solstice Quantum", "Argent Q Systems"},
            "biotech": {"Meridian Genomics", "Cascade Bio Diagnostics", "Orinthal Therapeutics"},
            "energy": {"Solvane Energy", "Fenwick Hydrogen"},
        }
        for domain, companies in by_domain.items():
            assert connected_companies & companies, f"No relation touches the {domain} cluster"


class TestSlugifyHelper:
    def test_simple_name(self, seed_module):
        assert seed_module._slugify("Nexora AI") == "nexora-ai"

    def test_removes_periods(self, seed_module):
        assert seed_module._slugify("Fenwick Hydrogen Inc.") == "fenwick-hydrogen-inc"

    def test_no_collision_across_all_demo_companies(self, seed_module):
        slugs = [seed_module._slugify(c["name"]) for c in seed_module.DEMO_COMPANIES]
        assert len(slugs) == len(set(slugs))
