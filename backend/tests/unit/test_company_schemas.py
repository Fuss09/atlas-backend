"""
Tests unitaires — Company schemas, slug generation, validators
"""

import pytest
from pydantic import ValidationError

from app.models.company import CompanyStatus, CompanyType
from app.schemas.company import (
    CompanyCreate,
    CompanySearchParams,
    CompanyUpdate,
    PaginatedResponse,
    _generate_slug,
)


class TestSlugGeneration:
    def test_simple_name(self):
        assert _generate_slug("NVIDIA Corporation") == "nvidia-corporation"

    def test_accented_characters(self):
        result = _generate_slug("Société Générale")
        assert result == "societe-generale"

    def test_special_characters_removed(self):
        result = _generate_slug("Apple Inc.")
        assert result == "apple-inc"

    def test_multiple_spaces(self):
        result = _generate_slug("Tesla   Inc")
        assert result == "tesla-inc"

    def test_already_lowercase(self):
        result = _generate_slug("microsoft")
        assert result == "microsoft"

    def test_numbers_kept(self):
        result = _generate_slug("3M Company")
        assert result == "3m-company"

    def test_long_name_truncated(self):
        long_name = "A" * 400
        result = _generate_slug(long_name)
        assert len(result) <= 280


class TestCompanyCreate:
    def test_minimal_valid(self):
        c = CompanyCreate(name="NVIDIA", country="US")
        assert c.name == "NVIDIA"
        assert c.country == "US"
        assert c.slug == "nvidia"

    def test_slug_auto_generated(self):
        c = CompanyCreate(name="Apple Inc", country="US")
        assert c.slug == "apple-inc"

    def test_custom_slug_respected(self):
        c = CompanyCreate(name="Apple Inc", country="US", slug="apple")
        assert c.slug == "apple"

    def test_ticker_normalized_to_uppercase(self):
        c = CompanyCreate(name="NVIDIA", country="US", ticker="nvda")
        assert c.ticker == "NVDA"

    def test_country_normalized_to_uppercase(self):
        c = CompanyCreate(name="NVIDIA", country="us")
        assert c.country == "US"

    def test_isin_valid(self):
        c = CompanyCreate(name="NVIDIA", country="US", isin="US67066G1040")
        assert c.isin == "US67066G1040"

    def test_isin_invalid_format(self):
        with pytest.raises(ValidationError) as exc_info:
            CompanyCreate(name="NVIDIA", country="US", isin="INVALID")
        assert "ISIN" in str(exc_info.value)

    def test_isin_normalized_to_uppercase(self):
        c = CompanyCreate(name="NVIDIA", country="US", isin="us67066g1040")
        assert c.isin == "US67066G1040"

    def test_website_https_added(self):
        c = CompanyCreate(name="NVIDIA", country="US", website="nvidia.com")
        assert c.website == "https://nvidia.com"

    def test_website_with_http_kept(self):
        c = CompanyCreate(name="NVIDIA", country="US", website="http://nvidia.com")
        assert c.website == "http://nvidia.com"

    def test_website_with_https_kept(self):
        c = CompanyCreate(name="NVIDIA", country="US", website="https://nvidia.com")
        assert c.website == "https://nvidia.com"

    def test_founded_year_too_old(self):
        with pytest.raises(ValidationError):
            CompanyCreate(name="Old", country="US", founded_year=1500)

    def test_founded_year_too_future(self):
        with pytest.raises(ValidationError):
            CompanyCreate(name="Future", country="US", founded_year=2200)

    def test_founded_year_valid(self):
        c = CompanyCreate(name="Old Company", country="US", founded_year=1899)
        assert c.founded_year == 1899

    def test_company_type_defaults_to_public(self):
        c = CompanyCreate(name="Company", country="US")
        assert c.company_type == CompanyType.PUBLIC

    def test_status_defaults_to_active(self):
        c = CompanyCreate(name="Company", country="US")
        assert c.status == CompanyStatus.ACTIVE

    def test_private_company_no_ticker(self):
        """Une entreprise privée peut ne pas avoir de ticker."""
        c = CompanyCreate(
            name="SpaceX",
            country="US",
            company_type=CompanyType.PRIVATE,
        )
        assert c.ticker is None
        assert c.company_type == CompanyType.PRIVATE


class TestCompanyUpdate:
    def test_all_fields_optional(self):
        """CompanyUpdate avec aucun champ ne doit pas lever d'erreur."""
        u = CompanyUpdate()
        assert u.model_dump(exclude_none=True) == {}

    def test_partial_update(self):
        u = CompanyUpdate(sector="Technology", employees=10000)
        data = u.model_dump(exclude_none=True)
        assert data == {"sector": "Technology", "employees": 10000}

    def test_ticker_normalized(self):
        u = CompanyUpdate(ticker="aapl")
        assert u.ticker == "AAPL"

    def test_country_normalized(self):
        u = CompanyUpdate(country="fr")
        assert u.country == "FR"


class TestPaginatedResponse:
    def test_basic_pagination(self):
        from app.schemas.company import CompanyListItem
        p = PaginatedResponse[str](items=["a", "b"], total=10, page=1, page_size=2)
        assert p.total == 10
        assert p.page == 1
        assert p.has_next is True
        assert p.has_prev is False

    def test_last_page(self):
        p = PaginatedResponse[str](items=["a"], total=10, page=5, page_size=2)
        assert p.has_next is False
        assert p.has_prev is True

    def test_total_pages_calculation(self):
        p = PaginatedResponse[str](items=[], total=21, page=1, page_size=10)
        assert p.total_pages == 3

    def test_single_page(self):
        p = PaginatedResponse[str](items=["a", "b"], total=2, page=1, page_size=10)
        assert p.total_pages == 1
        assert p.has_next is False
        assert p.has_prev is False


class TestCompanySearchParams:
    def test_defaults(self):
        params = CompanySearchParams()
        assert params.q is None
        assert params.status == CompanyStatus.ACTIVE

    def test_country_normalized(self):
        params = CompanySearchParams(country="us")
        assert params.country == "US"

    def test_q_max_length(self):
        with pytest.raises(ValidationError):
            CompanySearchParams(q="a" * 201)
