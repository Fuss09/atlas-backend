"""Tests unitaires — Event model, schemas, score logic"""

import pytest
from datetime import UTC, datetime, timedelta
from pydantic import ValidationError

from app.models.event import (
    EVENT_TYPE_SCORE_BOOST,
    IMPORTANCE_WEIGHTS,
    EventType,
    ImportanceLevel,
)
from app.schemas.event import EventCreate, EventUpdate
from app.services.event import _compute_score_boost


class TestImportanceWeights:
    def test_all_levels_have_weight(self):
        for level in ImportanceLevel:
            assert level in IMPORTANCE_WEIGHTS
            assert 0.0 < IMPORTANCE_WEIGHTS[level] <= 1.0

    def test_weights_ordered(self):
        assert IMPORTANCE_WEIGHTS[ImportanceLevel.LOW] < IMPORTANCE_WEIGHTS[ImportanceLevel.MEDIUM]
        assert IMPORTANCE_WEIGHTS[ImportanceLevel.MEDIUM] < IMPORTANCE_WEIGHTS[ImportanceLevel.HIGH]
        assert IMPORTANCE_WEIGHTS[ImportanceLevel.HIGH] < IMPORTANCE_WEIGHTS[ImportanceLevel.CRITICAL]

    def test_critical_is_max(self):
        assert IMPORTANCE_WEIGHTS[ImportanceLevel.CRITICAL] == 1.0


class TestEventTypeBoost:
    def test_fda_approval_is_highest(self):
        positive = {k: v for k, v in EVENT_TYPE_SCORE_BOOST.items() if v > 0}
        assert EVENT_TYPE_SCORE_BOOST[EventType.FDA_APPROVAL] == max(positive.values())

    def test_fda_rejection_is_negative(self):
        assert EVENT_TYPE_SCORE_BOOST[EventType.FDA_REJECTION] < 0

    def test_insider_sell_is_negative(self):
        assert EVENT_TYPE_SCORE_BOOST[EventType.INSIDER_SELL] < 0

    def test_all_types_have_boost(self):
        for t in EventType:
            assert t in EVENT_TYPE_SCORE_BOOST


class TestScoreBoost:
    def test_critical_fda_max_confidence(self):
        boost = _compute_score_boost(EventType.FDA_APPROVAL, ImportanceLevel.CRITICAL, 1.0)
        assert boost == round(20.0 * 1.0 * 1.0, 2)

    def test_low_news_low_confidence(self):
        boost = _compute_score_boost(EventType.NEWS, ImportanceLevel.LOW, 0.5)
        assert boost == round(2.0 * 0.25 * 0.5, 2)

    def test_rejection_gives_negative_boost(self):
        boost = _compute_score_boost(EventType.FDA_REJECTION, ImportanceLevel.HIGH, 1.0)
        assert boost < 0

    def test_confidence_zero_gives_zero(self):
        boost = _compute_score_boost(EventType.FUNDING, ImportanceLevel.HIGH, 0.0)
        assert boost == 0.0


class TestEventCreate:
    def test_valid_minimal(self):
        e = EventCreate(
            company_id="00000000-0000-0000-0000-000000000001",
            event_type=EventType.NEWS,
            title="Big news",
            occurred_at=datetime.now(UTC),
        )
        assert e.source == "manual"
        assert e.confidence_score == 1.0

    def test_title_too_short(self):
        with pytest.raises(ValidationError):
            EventCreate(
                company_id="00000000-0000-0000-0000-000000000001",
                event_type=EventType.NEWS,
                title="Hi",
                occurred_at=datetime.now(UTC),
            )

    def test_confidence_out_of_range(self):
        with pytest.raises(ValidationError):
            EventCreate(
                company_id="00000000-0000-0000-0000-000000000001",
                event_type=EventType.NEWS,
                title="Valid title",
                occurred_at=datetime.now(UTC),
                confidence_score=1.5,
            )

    def test_defaults(self):
        e = EventCreate(
            company_id="00000000-0000-0000-0000-000000000001",
            event_type=EventType.FUNDING,
            title="Series A raised",
            occurred_at=datetime.now(UTC),
        )
        assert e.importance == ImportanceLevel.MEDIUM
        assert e.confidence_score == 1.0
        assert e.raw_data is None


class TestEventUpdate:
    def test_all_optional(self):
        u = EventUpdate()
        assert u.model_dump(exclude_none=True) == {}

    def test_sentiment_range(self):
        with pytest.raises(ValidationError):
            EventUpdate(sentiment_score=1.5)

    def test_valid_sentiment(self):
        u = EventUpdate(sentiment_score=-0.5)
        assert u.sentiment_score == -0.5
