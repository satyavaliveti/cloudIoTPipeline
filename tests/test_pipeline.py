from datetime import UTC, datetime

import pytest

from app.models import TelemetryRecord
from app.pipeline import aggregate, clean


def payload(value: float = 21.5) -> dict:
    return {
        "device_id": "factory-1",
        "sensor_type": "temperature",
        "value": value,
        "unit": " C ",
        "recorded_at": "2026-01-02T10:15:00Z",
    }


def test_clean_normalizes_valid_record() -> None:
    record = clean(payload())
    assert record.unit == "c"
    assert record.recorded_at == datetime(2026, 1, 2, 10, 15, tzinfo=UTC)


def test_clean_rejects_outlier() -> None:
    with pytest.raises(ValueError, match="between"):
        clean(payload(500))


def test_aggregate_groups_hourly() -> None:
    records = [TelemetryRecord.model_validate(payload(20)), TelemetryRecord.model_validate(payload(24))]
    result = aggregate(records)
    assert len(result) == 1
    assert result[0].sample_count == 2
    assert result[0].average == 22
    assert result[0].window_start == datetime(2026, 1, 2, 10, tzinfo=UTC)
