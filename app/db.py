import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import get_settings
from app.models import Aggregate, TelemetryRecord

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


def save_records(records: list[TelemetryRecord]) -> None:
    if not records:
        return
    values = [
        (
            record.event_id,
            record.device_id,
            record.sensor_type,
            record.value,
            record.unit,
            record.recorded_at,
            record.ingested_at,
            json.dumps(record.metadata),
        )
        for record in records
    ]
    with connection() as conn, conn.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO telemetry
                (event_id, device_id, sensor_type, value, unit, recorded_at, ingested_at, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_id) DO NOTHING
            """,
            values,
        )


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
                sample_count = EXCLUDED.sample_count,
                minimum = EXCLUDED.minimum,
                maximum = EXCLUDED.maximum,
                average = EXCLUDED.average,
                updated_at = now()
            """,
            values,
        )


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


def healthcheck() -> bool:
    with connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT 1")
        return cursor.fetchone() == (1,)
