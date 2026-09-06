from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from domain.models.events import NormalizedEvent


def _base_kwargs(**overrides) -> dict:
    kwargs = dict(
        event_id="evt-1",
        timestamp=datetime.now(UTC),
        received_at=datetime.now(UTC),
        source="synthetic",
        event_category="identity",
        severity="medium",
        summary="synthetic authentication anomaly",
        raw_event_ref="raw-1",
    )
    kwargs.update(overrides)
    return kwargs


def test_valid_event_round_trips():
    event = NormalizedEvent(**_base_kwargs())
    assert event.event_id == "evt-1"
    assert event.severity == "medium"


def test_event_is_immutable():
    event = NormalizedEvent(**_base_kwargs())
    with pytest.raises(ValidationError):
        event.severity = "critical"  # type: ignore[misc]


@pytest.mark.parametrize(
    "field,value",
    [
        ("severity", "apocalyptic"),
        ("source", "not-a-real-sensor"),
        ("event_category", "not-a-real-category"),
        ("src_port", 0),
        ("src_port", 70000),
    ],
)
def test_rejects_invalid_enum_and_range_values(field, value):
    with pytest.raises(ValidationError):
        NormalizedEvent(**_base_kwargs(**{field: value}))


def test_rejects_oversized_summary():
    with pytest.raises(ValidationError):
        NormalizedEvent(**_base_kwargs(summary="x" * 5000))


def test_rejects_oversized_tag_list():
    with pytest.raises(ValidationError):
        NormalizedEvent(**_base_kwargs(tags=[f"tag-{i}" for i in range(200)]))
