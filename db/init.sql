CREATE TABLE IF NOT EXISTS telemetry (
    event_id UUID PRIMARY KEY,
    device_id VARCHAR(128) NOT NULL,
    sensor_type VARCHAR(32) NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit VARCHAR(24) NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS telemetry_device_recorded_idx
    ON telemetry (device_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS telemetry_sensor_recorded_idx
    ON telemetry (sensor_type, recorded_at DESC);

CREATE TABLE IF NOT EXISTS telemetry_hourly (
    device_id VARCHAR(128) NOT NULL,
    sensor_type VARCHAR(32) NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    sample_count INTEGER NOT NULL CHECK (sample_count > 0),
    minimum DOUBLE PRECISION NOT NULL,
    maximum DOUBLE PRECISION NOT NULL,
    average DOUBLE PRECISION NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (device_id, sensor_type, window_start)
);
