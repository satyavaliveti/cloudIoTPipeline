from datetime import UTC, datetime

from app.models import TelemetryRecord
from app.security import BehaviorBaseline, Severity, assess


def record(value: float) -> TelemetryRecord:
    return TelemetryRecord(
        device_id="pump-7",
        sensor_type="vibration",
        value=value,
        unit="mm/s",
        recorded_at=datetime(2026, 10, 15, 19, tzinfo=UTC),
    )


def test_welford_baseline_tracks_mean_and_variance() -> None:
    baseline = BehaviorBaseline(device_id="pump-7", sensor_type="vibration")
    for value in (1.0, 2.0, 3.0):
        baseline = baseline.observe(value)
    assert baseline.sample_count == 3
    assert baseline.mean == 2.0
    assert baseline.standard_deviation == 1.0


def test_anomaly_requires_a_mature_baseline() -> None:
    baseline = BehaviorBaseline(
        device_id="pump-7", sensor_type="vibration", sample_count=19, mean=2, m2=18
    )
    assert assess(record(20), baseline) is None


def test_deviation_creates_deterministic_critical_event() -> None:
    baseline = BehaviorBaseline(
        device_id="pump-7", sensor_type="vibration", sample_count=100, mean=2, m2=24.75
    )
    reading = record(12)
    first = assess(reading, baseline)
    second = assess(reading, baseline)
    assert first is not None
    assert first.severity == Severity.CRITICAL
    assert first.anomaly_score == 20.0
    assert second is not None
    assert first.event_id == second.event_id


def test_normal_reading_does_not_alert() -> None:
    baseline = BehaviorBaseline(
        device_id="pump-7", sensor_type="vibration", sample_count=100, mean=2, m2=99
    )
    assert assess(record(2.5), baseline) is None
