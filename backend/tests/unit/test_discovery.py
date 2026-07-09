"""Tests unitaires — Collectors, registry, discovery schemas"""

import pytest

from app.collectors.base import CompanyData
from app.collectors.registry import get_collector, list_available_sources
from app.collectors.sec import SIC_MAP, SecCollector
from app.collectors.ycombinator import YCombinatorCollector, _batch_to_year
from app.collectors.github import GitHubCollector, _parse_country, _extract_website
from app.models.company import CompanyType
from app.models.discovery import DiscoverySourceName
from app.schemas.discovery import TriggerJobRequest, DiscoveryJobResponse


class TestRegistry:
    def test_get_known_collector(self):
        c = get_collector(DiscoverySourceName.SEC)
        assert isinstance(c, SecCollector)

    def test_get_github_collector(self):
        c = get_collector(DiscoverySourceName.GITHUB)
        assert isinstance(c, GitHubCollector)

    def test_get_yc_collector(self):
        c = get_collector(DiscoverySourceName.YCOMBINATOR)
        assert isinstance(c, YCombinatorCollector)

    def test_unknown_source_raises(self):
        with pytest.raises(ValueError, match="No collector registered"):
            get_collector("nonexistent")  # type: ignore

    def test_list_sources_contains_implemented(self):
        sources = list_available_sources()
        implemented = [s for s in sources if s["implemented"]]
        names = [s["source"] for s in implemented]
        assert "sec" in names
        assert "github" in names
        assert "ycombinator" in names
        assert "crunchbase" in names

    def test_list_sources_contains_future(self):
        sources = list_available_sources()
        not_impl = [s for s in sources if not s["implemented"]]
        names = [s["source"] for s in not_impl]
        assert "fda" in names
        assert "arxiv" in names

    def test_get_with_params(self):
        c = get_collector(DiscoverySourceName.SEC, params={"limit": 10})
        assert c.params["limit"] == 10


class TestCompanyData:
    def test_defaults(self):
        d = CompanyData(name="Test Corp", country="US")
        assert d.company_type == CompanyType.PUBLIC
        assert d.tags == []
        assert d.raw_data == {}

    def test_tags_default_empty_list(self):
        d1 = CompanyData(name="A", country="US")
        d2 = CompanyData(name="B", country="US")
        d1.tags.append("tag1")
        assert "tag1" not in d2.tags  # pas de shared mutable default


class TestSecCollector:
    def test_source_name(self):
        c = SecCollector()
        assert c.source_name == DiscoverySourceName.SEC

    def test_sic_map_technology(self):
        assert SIC_MAP["3674"] == ("Technology", "Semiconductors")
        assert SIC_MAP["7372"] == ("Technology", "Software")

    def test_sic_map_healthcare(self):
        assert SIC_MAP["2836"] == ("Healthcare", "Biologics & Pharmaceuticals")

    def test_context_manager_requires_async(self):
        """Le collecteur doit être utilisé comme context manager."""
        c = SecCollector()
        with pytest.raises(RuntimeError, match="context manager"):
            _ = c.client


class TestYCombinatorCollector:
    def test_source_name(self):
        c = YCombinatorCollector()
        assert c.source_name == DiscoverySourceName.YCOMBINATOR

    def test_batch_to_year_winter(self):
        assert _batch_to_year("W23") == 2023

    def test_batch_to_year_summer(self):
        assert _batch_to_year("S22") == 2022

    def test_batch_to_year_four_digits(self):
        assert _batch_to_year("W2024") == 2024

    def test_batch_to_year_none(self):
        assert _batch_to_year(None) is None
        assert _batch_to_year("") is None

    def test_batch_to_year_invalid(self):
        assert _batch_to_year("IK12") is None  # hors plage 2005-2030

    def test_normalize_minimal(self):
        c = YCombinatorCollector()
        entry = {"name": "Stripe", "slug": "stripe", "status": "Active"}
        result = c._normalize(entry)
        assert result is not None
        assert result.name == "Stripe"
        assert result.country == "US"
        assert "ycombinator" in result.tags

    def test_normalize_missing_name(self):
        c = YCombinatorCollector()
        result = c._normalize({"slug": "no-name"})
        assert result is None


class TestGitHubCollector:
    def test_source_name(self):
        c = GitHubCollector()
        assert c.source_name == DiscoverySourceName.GITHUB

    def test_parse_country_us(self):
        assert _parse_country("San Francisco, CA") == "US"
        assert _parse_country("United States") == "US"

    def test_parse_country_uk(self):
        assert _parse_country("London, UK") == "GB"

    def test_parse_country_france(self):
        assert _parse_country("Paris, France") == "FR"

    def test_parse_country_unknown_defaults_us(self):
        assert _parse_country("Unknown Planet") == "US"

    def test_parse_country_none(self):
        assert _parse_country(None) == "US"

    def test_extract_website_adds_https(self):
        assert _extract_website("example.com") == "https://example.com"

    def test_extract_website_keeps_https(self):
        assert _extract_website("https://example.com") == "https://example.com"

    def test_extract_website_keeps_http(self):
        assert _extract_website("http://example.com") == "http://example.com"

    def test_extract_website_none(self):
        assert _extract_website(None) is None
        assert _extract_website("") is None

    def test_normalize_org(self):
        c = GitHubCollector()
        org = {
            "login": "microsoft",
            "name": "Microsoft",
            "description": "Open source from Microsoft",
            "location": "Redmond, WA",
            "blog": "https://microsoft.com",
            "public_repos": 4000,
            "followers": 300000,
        }
        result = c._normalize(org)
        assert result is not None
        assert result.name == "Microsoft"
        assert result.country == "US"
        assert result.website == "https://microsoft.com"
        assert "open-source" in result.tags
        assert "high-activity" in result.tags
        assert "popular" in result.tags

    def test_normalize_missing_name(self):
        c = GitHubCollector()
        result = c._normalize({"login": "no-name-org"})
        # login est utilisé comme fallback
        assert result is not None
        assert result.name == "no-name-org"


class TestDiscoverySchemas:
    def test_trigger_job_request(self):
        r = TriggerJobRequest(source=DiscoverySourceName.SEC)
        assert r.source == DiscoverySourceName.SEC
        assert r.params == {}

    def test_trigger_job_with_params(self):
        r = TriggerJobRequest(source=DiscoverySourceName.GITHUB, params={"limit": 100})
        assert r.params["limit"] == 100
