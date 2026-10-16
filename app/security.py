from datetime import UTC, datetime
from enum import StrEnum
from math import sqrt
from uuid import UUID, uuid5

from pydantic import BaseModel, Field

from app.models import SensorType, TelemetryRecord

SECURITY_EVENT_NAMESPACE = UUID("ae6b65bc-1881-4a55-82ad-8d38cfaab1d8")


class Severity(StrEnum):
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BehaviorBaseline(BaseModel):
    device_id: str
    sensor_type: SensorType
    sample_count: int = 0
    mean: float = 0.0
    m2: float = 0.0

    @property
    def standard_deviation(self) -> float:
        return sqrt(self.m2 / (self.sample_count - 1)) if self.sample_count > 1 else 0.0

    def observe(self, value: float) -> "BehaviorBaseline":
        count = self.sample_count + 1
        delta = value - self.mean
        mean = self.mean + delta / count
        m2 = self.m2 + delta * (value - mean)
        return self.model_copy(update={"sample_count": count, "mean": mean, "m2": m2})


class SecurityEvent(BaseModel):
    event_id: UUID
    telemetry_event_id: UUID
    device_id: str
    sensor_type: SensorType
    severity: Severity
    anomaly_score: float
    observed_value: float
    baseline_mean: float
    baseline_stddev: float
    reason: str
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def assess(
    record: TelemetryRecord,
    baseline: BehaviorBaseline,
    *,
    minimum_samples: int = 20,
    threshold: float = 3.5,
) -> SecurityEvent | None:
    """Score a reading against its prior baseline without contaminating that baseline."""
    if baseline.sample_count < minimum_samples:
        return None

    stddev = baseline.standard_deviation
    difference = abs(record.value - baseline.mean)
    score = difference / stddev if stddev > 1e-9 else (999.0 if difference > 1e-9 else 0.0)
    if score < threshold:
        return None

    severity = Severity.MEDIUM
    if score >= 8:
        severity = Severity.CRITICAL
    elif score >= 5:
        severity = Severity.HIGH

    return SecurityEvent(
        event_id=uuid5(SECURITY_EVENT_NAMESPACE, str(record.event_id)),
        telemetry_event_id=record.event_id,
        device_id=record.device_id,
        sensor_type=record.sensor_type,
        severity=severity,
        anomaly_score=round(score, 4),
        observed_value=record.value,
        baseline_mean=baseline.mean,
        baseline_stddev=stddev,
        reason=f"Reading deviates {score:.2f} standard deviations from device baseline",
    )
