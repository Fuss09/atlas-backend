"""Tests unitaires — Theme schemas et logique"""

import pytest
from pydantic import ValidationError

from app.models.theme import MaturityLevel
from app.schemas.theme import ThemeCreate, ThemeUpdate, _generate_theme_slug


class TestThemeSlug:
    def test_simple(self):
        assert _generate_theme_slug("Artificial Intelligence") == "artificial-intelligence"

    def test_accents(self):
        assert _generate_theme_slug("Énergie Nucléaire") == "energie-nucleaire"

    def test_ampersand_removed(self):
        result = _generate_theme_slug("Defense & Aerospace")
        assert result == "defense-aerospace"

    def test_numbers(self):
        assert _generate_theme_slug("5G Networks") == "5g-networks"


class TestThemeCreate:
    def test_minimal_valid(self):
        t = ThemeCreate(name="AI", maturity_level=MaturityLevel.EMERGING)
        assert t.slug == "ai"
        assert t.is_active is True

    def test_slug_auto_generated(self):
        t = ThemeCreate(name="Quantum Computing")
        assert t.slug == "quantum-computing"

    def test_custom_slug_kept(self):
        t = ThemeCreate(name="AI", slug="my-ai-slug")
        assert t.slug == "my-ai-slug"

    def test_valid_hex_color(self):
        t = ThemeCreate(name="AI", color="#6366f1")
        assert t.color == "#6366f1"

    def test_hex_color_normalized_lowercase(self):
        t = ThemeCreate(name="AI", color="#6366F1")
        assert t.color == "#6366f1"

    def test_invalid_hex_color(self):
        with pytest.raises(ValidationError) as exc:
            ThemeCreate(name="AI", color="blue")
        assert "hex" in str(exc.value).lower()

    def test_invalid_short_hex(self):
        with pytest.raises(ValidationError):
            ThemeCreate(name="AI", color="#fff")

    def test_name_too_short(self):
        with pytest.raises(ValidationError):
            ThemeCreate(name="A")

    def test_defaults(self):
        t = ThemeCreate(name="Test Theme")
        assert t.maturity_level == MaturityLevel.EMERGING
        assert t.is_active is True
        assert t.color is None
        assert t.icon is None


class TestThemeUpdate:
    def test_all_optional(self):
        u = ThemeUpdate()
        assert u.model_dump(exclude_none=True) == {}

    def test_partial_update(self):
        u = ThemeUpdate(maturity_level=MaturityLevel.GROWTH, is_active=False)
        data = u.model_dump(exclude_none=True)
        assert data["maturity_level"] == MaturityLevel.GROWTH
        assert data["is_active"] is False

    def test_invalid_color_update(self):
        with pytest.raises(ValidationError):
            ThemeUpdate(color="not-a-color")
