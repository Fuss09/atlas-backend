"""Tests unitaires — OpportunityEngine (moteur pur, sans DB)"""

from datetime import UTC, datetime, timedelta

import pytest

from app.engines.opportunity import (
    CompanySignal,
    ConvictionLevel,
    DiscoverySignal,
    EventSignal,
    OpportunityEngine,
    OpportunityStage,
    ScoreComponent,
    ThemeSignal,
)

NOW = datetime(2026, 7, 6, tzinfo=UTC)


def _company(**overrides) -> CompanySignal:
    base = dict(
        has_description=True,
        has_website=True,
        has_sector=True,
        has_industry=True,
        has_employees=True,
        has_revenue=True,
        has_market_cap=True,
        has_founded_year=True,
        has_logo=True,
        is_featured=False,
        status="active",
    )
    base.update(overrides)
    return CompanySignal(**base)


class TestScoreComponent:
    def test_contribution_is_value_times_weight(self):
        c = ScoreComponent(name="x", value=80.0, weight=0.5)
        assert c.contribution == 40.0

    def test_contribution_is_zero_when_not_connected(self):
        c = ScoreComponent(name="market_signals", value=None, weight=0.0)
        assert c.contribution == 0.0


class TestEmptyCompany:
    def test_no_signals_gives_low_score(self):
        engine = OpportunityEngine()
        result = engine.compute(
            events=[], themes=[], company=_company(), discoveries=[], now=NOW
        )
        assert result.score < 40
        assert result.conviction == ConvictionLevel.LOW
        assert result.stage == OpportunityStage.EARLY
        assert "Aucun événement" in " ".join(result.negative_factors)

    def test_market_signals_always_present_but_not_connected(self):
        engine = OpportunityEngine()
        result = engine.compute(
            events=[], themes=[], company=_company(), discoveries=[], now=NOW
        )
        market = result.components["market_signals"]
        assert market.value is None
        assert market.is_connected is False
        assert market.contribution == 0.0


class TestEventsComponent:
    def test_recent_high_impact_events_boost_score(self):
        engine = OpportunityEngine()
        events = [
            EventSignal("fda_approval", "critical", NOW - timedelta(days=2), score_boost=20.0),
            EventSignal("funding", "high", NOW - timedelta(days=5), score_boost=9.0),
        ]
        result = engine.compute(
            events=events, themes=[], company=_company(), discoveries=[], now=NOW
        )
        assert result.components["events"].value > 20
        assert any("Fda Approval" in f for f in result.positive_factors)

    def test_old_events_decay(self):
        engine = OpportunityEngine()
        recent = [EventSignal("funding", "high", NOW - timedelta(days=1), score_boost=10.0)]
        old = [EventSignal("funding", "high", NOW - timedelta(days=365), score_boost=10.0)]

        recent_result = engine.compute(
            events=recent, themes=[], company=_company(), discoveries=[], now=NOW
        )
        old_result = engine.compute(
            events=old, themes=[], company=_company(), discoveries=[], now=NOW
        )
        assert recent_result.components["events"].value > old_result.components["events"].value

    def test_negative_events_reduce_score(self):
        engine = OpportunityEngine()
        events = [EventSignal("fda_rejection", "critical", NOW - timedelta(days=1), score_boost=-15.0)]
        result = engine.compute(
            events=events, themes=[], company=_company(), discoveries=[], now=NOW
        )
        assert result.components["events"].value == 0.0
        assert any("Fda Rejection" in f for f in result.negative_factors)


class TestThemeStrengthComponent:
    def test_emerging_theme_scores_higher_than_mature(self):
        engine = OpportunityEngine()
        emerging = engine.compute(
            events=[], themes=[ThemeSignal("Quantum Computing", "emerging")],
            company=_company(), discoveries=[], now=NOW,
        )
        mature = engine.compute(
            events=[], themes=[ThemeSignal("Legacy Tech", "mature")],
            company=_company(), discoveries=[], now=NOW,
        )
        assert (
            emerging.components["theme_strength"].value
            > mature.components["theme_strength"].value
        )

    def test_multiple_themes_get_diversification_bonus(self):
        engine = OpportunityEngine()
        one_theme = engine.compute(
            events=[], themes=[ThemeSignal("AI", "growth")],
            company=_company(), discoveries=[], now=NOW,
        )
        three_themes = engine.compute(
            events=[],
            themes=[
                ThemeSignal("AI", "growth"),
                ThemeSignal("Robotics", "growth"),
                ThemeSignal("Defense", "growth"),
            ],
            company=_company(), discoveries=[], now=NOW,
        )
        assert (
            three_themes.components["theme_strength"].value
            > one_theme.components["theme_strength"].value
        )

    def test_no_theme_is_penalized(self):
        engine = OpportunityEngine()
        result = engine.compute(
            events=[], themes=[], company=_company(), discoveries=[], now=NOW
        )
        assert "Aucun thème" in " ".join(result.negative_factors)


class TestCompanyQualityComponent:
    def test_complete_profile_scores_high(self):
        engine = OpportunityEngine()
        result = engine.compute(
            events=[], themes=[], company=_company(), discoveries=[], now=NOW
        )
        assert result.components["company_quality"].value == 100.0

    def test_incomplete_profile_scores_lower(self):
        engine = OpportunityEngine()
        incomplete = _company(has_revenue=False, has_market_cap=False, has_logo=False)
        result = engine.compute(
            events=[], themes=[], company=incomplete, discoveries=[], now=NOW
        )
        assert result.components["company_quality"].value < 100.0
        assert len(result.components["company_quality"].negative_factors) == 3

    def test_inactive_company_is_penalized(self):
        engine = OpportunityEngine()
        active = engine.compute(
            events=[], themes=[], company=_company(), discoveries=[], now=NOW
        )
        inactive = engine.compute(
            events=[], themes=[], company=_company(status="inactive"), discoveries=[], now=NOW
        )
        assert (
            inactive.components["company_quality"].value
            < active.components["company_quality"].value
        )

    def test_featured_gets_small_bonus(self):
        engine = OpportunityEngine()
        featured = engine.compute(
            events=[], themes=[], company=_company(is_featured=True), discoveries=[], now=NOW
        )
        assert featured.components["company_quality"].value == 100.0  # capped at 100
        assert any("mise en avant" in f for f in featured.components["company_quality"].positive_factors)


class TestDiscoverySignalsComponent:
    def test_multi_source_corroboration_scores_higher(self):
        engine = OpportunityEngine()
        single = engine.compute(
            events=[], themes=[], company=_company(),
            discoveries=[DiscoverySignal("sec", NOW - timedelta(days=1))], now=NOW,
        )
        multi = engine.compute(
            events=[], themes=[], company=_company(),
            discoveries=[
                DiscoverySignal("sec", NOW - timedelta(days=1)),
                DiscoverySignal("github", NOW - timedelta(days=1)),
                DiscoverySignal("crunchbase", NOW - timedelta(days=1)),
            ],
            now=NOW,
        )
        assert (
            multi.components["discovery_signals"].value
            > single.components["discovery_signals"].value
        )

    def test_stale_discovery_scores_lower_than_fresh(self):
        engine = OpportunityEngine()
        fresh = engine.compute(
            events=[], themes=[], company=_company(),
            discoveries=[DiscoverySignal("sec", NOW - timedelta(days=1))], now=NOW,
        )
        stale = engine.compute(
            events=[], themes=[], company=_company(),
            discoveries=[DiscoverySignal("sec", NOW - timedelta(days=400))], now=NOW,
        )
        assert (
            fresh.components["discovery_signals"].value
            > stale.components["discovery_signals"].value
        )


class TestConvictionLevels:
    @pytest.mark.parametrize(
        "score,expected",
        [(10, ConvictionLevel.LOW), (45, ConvictionLevel.MODERATE),
         (65, ConvictionLevel.HIGH), (85, ConvictionLevel.VERY_HIGH)],
    )
    def test_conviction_thresholds(self, score, expected):
        engine = OpportunityEngine()
        assert engine._conviction_from_score(score) == expected


class TestOpportunityStage:
    def test_no_events_is_early(self):
        engine = OpportunityEngine()
        result = engine.compute(
            events=[], themes=[], company=_company(), discoveries=[], now=NOW
        )
        assert result.stage == OpportunityStage.EARLY

    def test_many_recent_events_with_high_score_is_acceleration(self):
        engine = OpportunityEngine()
        events = [
            EventSignal("fda_approval", "critical", NOW - timedelta(days=1), score_boost=20.0),
            EventSignal("acquisition", "critical", NOW - timedelta(days=5), score_boost=15.0),
            EventSignal("partnership", "high", NOW - timedelta(days=10), score_boost=8.0),
        ]
        result = engine.compute(
            events=events,
            themes=[ThemeSignal("AI", "emerging")],
            company=_company(),
            discoveries=[DiscoverySignal("sec", NOW - timedelta(days=1))],
            now=NOW,
        )
        assert result.stage == OpportunityStage.ACCELERATION

    def test_mature_theme_with_no_recent_signal_is_mature_stage(self):
        engine = OpportunityEngine()
        events = [EventSignal("news", "low", NOW - timedelta(days=200), score_boost=2.0)]
        result = engine.compute(
            events=events,
            themes=[ThemeSignal("Legacy Tech", "mature")],
            company=_company(),
            discoveries=[],
            now=NOW,
        )
        assert result.stage == OpportunityStage.MATURE


class TestDeterminism:
    def test_same_input_gives_same_output(self):
        engine = OpportunityEngine()
        events = [EventSignal("funding", "high", NOW - timedelta(days=3), score_boost=9.0)]
        themes = [ThemeSignal("AI", "growth")]
        discoveries = [DiscoverySignal("ycombinator", NOW - timedelta(days=10))]

        r1 = engine.compute(events, themes, _company(), discoveries, now=NOW)
        r2 = engine.compute(events, themes, _company(), discoveries, now=NOW)
        assert r1.score == r2.score
        assert r1.conviction == r2.conviction
        assert r1.stage == r2.stage

    def test_score_always_within_bounds(self):
        engine = OpportunityEngine()
        events = [
            EventSignal("fda_approval", "critical", NOW - timedelta(days=1), score_boost=20.0)
            for _ in range(20)
        ]
        result = engine.compute(
            events=events,
            themes=[ThemeSignal("AI", "emerging")] * 5,
            company=_company(is_featured=True),
            discoveries=[DiscoverySignal("sec", NOW)],
            now=NOW,
        )
        assert 0 <= result.score <= 100
