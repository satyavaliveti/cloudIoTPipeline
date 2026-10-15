from fastapi.testclient import TestClient

from app.main import app, get_publisher


class FakePublisher:
    def publish(self, items):
        return len(items), ["record-1"]


def test_ingest_telemetry() -> None:
    app.dependency_overrides[get_publisher] = FakePublisher
    with TestClient(app) as client:
        response = client.post(
            "/v1/telemetry",
            json={
                "device_id": "device-42",
                "sensor_type": "humidity",
                "value": 55.2,
                "unit": "%",
                "recorded_at": "2026-01-02T10:15:00Z",
            },
        )
    app.dependency_overrides.clear()
    assert response.status_code == 202
    assert response.json() == {"accepted": 1, "failed": 0, "request_ids": ["record-1"]}


def test_rejects_invalid_telemetry() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v1/telemetry",
            json={
                "device_id": "",
                "sensor_type": "humidity",
                "value": 10,
                "unit": "%",
            },
        )
    assert response.status_code == 422
