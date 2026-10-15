import base64
import json
import logging
from typing import Any

from app.db import ensure_schema, save_aggregates, save_records
from app.models import TelemetryRecord
from app.pipeline import aggregate, clean, to_wire

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: dict[str, Any], _context: Any) -> dict[str, list[dict[str, str]]]:
    """Transform a Firehose batch, persist clean rows, and return S3-ready JSON lines."""
    output: list[dict[str, str]] = []
    cleaned: list[TelemetryRecord] = []

    for source in event.get("records", []):
        try:
            raw = base64.b64decode(source["data"]).decode().strip()
            record = clean(json.loads(raw))
            cleaned.append(record)
            output.append(
                {
                    "recordId": source["recordId"],
                    "result": "Ok",
                    "data": base64.b64encode(to_wire(record)).decode(),
                }
            )
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            logger.warning("Dropping invalid record %s: %s", source.get("recordId"), exc)
            output.append(
                {
                    "recordId": source.get("recordId", "unknown"),
                    "result": "Dropped",
                    "data": source.get("data", ""),
                }
            )

    if cleaned:
        try:
            ensure_schema()
            save_records(cleaned)
            save_aggregates(aggregate(cleaned))
        except Exception:
            # Raising makes Firehose retry instead of silently losing database writes.
            logger.exception("Database write failed")
            raise

    return {"records": output}
