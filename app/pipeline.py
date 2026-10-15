import json
from collections import defaultdict
from datetime import UTC, datetime
from statistics import fmean
from typing import Any

import boto3

from app.config import get_settings
from app.db import save_records
from app.models import Aggregate, TelemetryIn, TelemetryRecord

BOUNDS = {
    "temperature": (-100.0, 200.0),
    "humidity": (0.0, 100.0),
    "pressure": (100.0, 1500.0),
    "air_quality": (0.0, 1000.0),
    "vibration": (0.0, 100.0),
}


def clean(payload: dict[str, Any]) -> TelemetryRecord:
    record = TelemetryRecord.model_validate(payload)
    low, high = BOUNDS[record.sensor_type]
    if not low <= record.value <= high:
        raise ValueError(f"{record.sensor_type} value must be between {low} and {high}")
    record.unit = record.unit.strip().lower()
    return record


def aggregate(records: list[TelemetryRecord]) -> list[Aggregate]:
    groups: dict[tuple, list[TelemetryRecord]] = defaultdict(list)
    for record in records:
        window = record.recorded_at.replace(minute=0, second=0, microsecond=0)
        groups[(record.device_id, record.sensor_type, window)].append(record)
    return [
        Aggregate(
            device_id=device_id,
            sensor_type=sensor_type,
            window_start=window,
            sample_count=len(items),
            minimum=min(item.value for item in items),
            maximum=max(item.value for item in items),
            average=fmean(item.value for item in items),
        )
        for (device_id, sensor_type, window), items in groups.items()
    ]


def to_wire(record: TelemetryRecord) -> bytes:
    return (record.model_dump_json() + "\n").encode()


class Publisher:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = boto3.client("firehose", region_name=self.settings.aws_region)

    def publish(self, items: list[TelemetryIn]) -> tuple[int, list[str]]:
        records = [TelemetryRecord(**item.model_dump()) for item in items]
        if self.settings.local_processing:
            cleaned = [clean(record.model_dump()) for record in records]
            save_records(cleaned)
            return len(cleaned), [str(record.event_id) for record in cleaned]

        response = self.client.put_record_batch(
            DeliveryStreamName=self.settings.firehose_stream_name,
            Records=[{"Data": to_wire(record)} for record in records],
        )
        failed = response.get("FailedPutCount", 0)
        request_ids = [
            result["RecordId"]
            for result in response.get("RequestResponses", [])
            if "RecordId" in result
        ]
        return len(records) - failed, request_ids


def json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    return str(value)


def aggregate_to_json(item: Aggregate) -> str:
    return json.dumps(item.model_dump(), default=json_default)
