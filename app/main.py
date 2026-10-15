from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status

from app.config import Settings, get_settings
from app.db import close_pool, healthcheck, latest_records
from app.models import IngestResponse, TelemetryIn
from app.pipeline import Publisher


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    close_pool()


app = FastAPI(
    title="IoT Telemetry Pipeline",
    version="1.0.0",
    description="Ingests sensor events into Amazon Data Firehose for real-time ETL.",
    lifespan=lifespan,
)


def get_publisher() -> Publisher:
    return Publisher()


@app.get("/health")
def health(settings: Annotated[Settings, Depends(get_settings)]) -> dict:
    result = {"status": "ok", "environment": settings.environment}
    if settings.local_processing:
        try:
            result["database"] = "ok" if healthcheck() else "unavailable"
        except Exception:
            result["database"] = "unavailable"
            result["status"] = "degraded"
    return result


@app.post("/v1/telemetry", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
def ingest(
    telemetry: TelemetryIn,
    publisher: Annotated[Publisher, Depends(get_publisher)],
) -> IngestResponse:
    return ingest_batch([telemetry], publisher)


@app.post(
    "/v1/telemetry/batch", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED
)
def ingest_batch(
    telemetry: list[TelemetryIn],
    publisher: Annotated[Publisher, Depends(get_publisher)],
) -> IngestResponse:
    if not telemetry or len(telemetry) > 500:
        raise HTTPException(status_code=400, detail="batch must contain 1 to 500 records")
    try:
        accepted, request_ids = publisher.publish(telemetry)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="telemetry stream unavailable") from exc
    return IngestResponse(
        accepted=accepted,
        failed=len(telemetry) - accepted,
        request_ids=request_ids,
    )


@app.get("/v1/telemetry")
def get_telemetry(
    device_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> list[dict]:
    try:
        return latest_records(device_id, limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
