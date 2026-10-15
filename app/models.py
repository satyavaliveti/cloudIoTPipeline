from datetime import UTC, datetime
from enum import StrEnum
from math import isfinite
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class SensorType(StrEnum):
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    PRESSURE = "pressure"
    AIR_QUALITY = "air_quality"
    VIBRATION = "vibration"


class TelemetryIn(BaseModel):
    device_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    sensor_type: SensorType
    value: float
    unit: str = Field(min_length=1, max_length=24)
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("value")
    @classmethod
    def finite_value(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("value must be finite")
        return value

    @field_validator("recorded_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("recorded_at must include a timezone")
        return value.astimezone(UTC)


class TelemetryRecord(TelemetryIn):
    event_id: UUID = Field(default_factory=uuid4)
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class IngestResponse(BaseModel):
    accepted: int
    failed: int = 0
    request_ids: list[str] = Field(default_factory=list)


class Aggregate(BaseModel):
    device_id: str
    sensor_type: SensorType
    window_start: datetime
    sample_count: int
    minimum: float
    maximum: float
    average: float
