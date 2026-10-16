import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import get_settings
from app.models import Aggregate, TelemetryRecord
from app.security import BehaviorBaseline, SecurityEvent, assess

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(get_settings().database_url, min_size=1, max_size=10, open=False)
        _pool.open()
    return _pool


@contextmanager
def connection() -> Iterator[Connection]:
    with get_pool().connection() as conn:
        yield conn


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def ensure_schema() -> None:
    migration = Path(__file__).parents[1] / "db" / "init.sql"
    with connection() as conn, conn.cursor() as cursor:
        cursor.execute(migration.read_text(encoding="utf-8"))


def save_records(records: list[TelemetryRecord]) -> list[TelemetryRecord]:
    if not records:
        return []
    inserted: list[TelemetryRecord] = []
    with connection() as conn, conn.cursor() as cursor:
        for record in records:
            cursor.execute(
                """
                INSERT INTO telemetry
                    (event_id, device_id, sensor_type, value, unit,
                     recorded_at, ingested_at, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_id) DO NOTHING
                RETURNING event_id
                """,
                (
                    record.event_id,
                    record.device_id,
                    record.sensor_type,
                    record.value,
                    record.unit,
                    record.recorded_at,
                    record.ingested_at,
                    json.dumps(record.metadata),
                ),
            )
            if cursor.fetchone():
                inserted.append(record)
    return inserted


def save_aggregates(items: list[Aggregate]) -> None:
    if not items:
        return
    values = [
        (
            item.device_id,
            item.sensor_type,
            item.window_start,
            item.sample_count,
            item.minimum,
            item.maximum,
            item.average,
        )
        for item in items
    ]
    with connection() as conn, conn.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO telemetry_hourly
                (device_id, sensor_type, window_start, sample_count, minimum, maximum, average)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (device_id, sensor_type, window_start) DO UPDATE SET
                average = (
                    telemetry_hourly.average * telemetry_hourly.sample_count
                    + EXCLUDED.average * EXCLUDED.sample_count
                ) / (telemetry_hourly.sample_count + EXCLUDED.sample_count),
                sample_count = telemetry_hourly.sample_count + EXCLUDED.sample_count,
                minimum = LEAST(telemetry_hourly.minimum, EXCLUDED.minimum),
                maximum = GREATEST(telemetry_hourly.maximum, EXCLUDED.maximum),
                updated_at = now()
            """,
            values,
        )


def detect_and_update_baselines(records: list[TelemetryRecord]) -> list[SecurityEvent]:
    events: list[SecurityEvent] = []
    with connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        for record in records:
            baseline_key = f"{record.device_id}:{record.sensor_type}"
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (baseline_key,))
            cursor.execute(
                "SELECT baseline_processed FROM telemetry WHERE event_id = %s FOR UPDATE",
                (record.event_id,),
            )
            telemetry_row = cursor.fetchone()
            if not telemetry_row or telemetry_row["baseline_processed"]:
                continue
            cursor.execute(
                """
                SELECT device_id, sensor_type, sample_count, mean, m2
                FROM device_baselines
                WHERE device_id = %s AND sensor_type = %s
                """,
                (record.device_id, record.sensor_type),
            )
            row = cursor.fetchone()
            baseline = (
                BehaviorBaseline.model_validate(row)
                if row
                else BehaviorBaseline(device_id=record.device_id, sensor_type=record.sensor_type)
            )
            security_event = assess(record, baseline)
            if security_event:
                events.append(security_event)
                cursor.execute(
                    """
                    INSERT INTO security_events
                        (event_id, telemetry_event_id, device_id, sensor_type, severity,
                         anomaly_score, observed_value, baseline_mean, baseline_stddev,
                         reason, detected_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (event_id) DO NOTHING
                    """,
                    (
                        security_event.event_id,
                        security_event.telemetry_event_id,
                        security_event.device_id,
                        security_event.sensor_type,
                        security_event.severity,
                        security_event.anomaly_score,
                        security_event.observed_value,
                        security_event.baseline_mean,
                        security_event.baseline_stddev,
                        security_event.reason,
                        security_event.detected_at,
                    ),
                )
            # Do not let anomalous readings poison the learned normal baseline.
            updated = baseline if security_event else baseline.observe(record.value)
            cursor.execute(
                """
                INSERT INTO device_baselines
                    (device_id, sensor_type, sample_count, mean, m2)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (device_id, sensor_type) DO UPDATE SET
                    sample_count = EXCLUDED.sample_count,
                    mean = EXCLUDED.mean,
                    m2 = EXCLUDED.m2,
                    updated_at = now()
                """,
                (
                    updated.device_id,
                    updated.sensor_type,
                    updated.sample_count,
                    updated.mean,
                    updated.m2,
                ),
            )
            cursor.execute(
                "UPDATE telemetry SET baseline_processed = true WHERE event_id = %s",
                (record.event_id,),
            )
    return events


def latest_records(device_id: str | None, limit: int) -> list[dict]:
    where = "WHERE device_id = %s" if device_id else ""
    params = (device_id, limit) if device_id else (limit,)
    with connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            f"""
            SELECT event_id, device_id, sensor_type, value, unit,
                   recorded_at, ingested_at, metadata
            FROM telemetry {where}
            ORDER BY recorded_at DESC LIMIT %s
            """,  # noqa: S608 -- where is selected from a constant
            params,
        )
        return list(cursor.fetchall())


def latest_security_events(device_id: str | None, limit: int) -> list[dict]:
    where = "WHERE device_id = %s" if device_id else ""
    params = (device_id, limit) if device_id else (limit,)
    with connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            f"""
            SELECT event_id, telemetry_event_id, device_id, sensor_type, severity,
                   anomaly_score, observed_value, baseline_mean, baseline_stddev,
                   reason, detected_at
            FROM security_events {where}
            ORDER BY detected_at DESC LIMIT %s
            """,  # noqa: S608 -- where is selected from a constant
            params,
        )
        return list(cursor.fetchall())


def security_events_for_records(records: list[TelemetryRecord]) -> list[SecurityEvent]:
    if not records:
        return []
    event_ids = [record.event_id for record in records]
    with connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT event_id, telemetry_event_id, device_id, sensor_type, severity,
                   anomaly_score, observed_value, baseline_mean, baseline_stddev,
                   reason, detected_at
            FROM security_events
            WHERE telemetry_event_id = ANY(%s)
            """,
            (event_ids,),
        )
        return [SecurityEvent.model_validate(row) for row in cursor.fetchall()]


def healthcheck() -> bool:
    with connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT 1")
        return cursor.fetchone() == (1,)
