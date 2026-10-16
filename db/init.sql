CREATE TABLE IF NOT EXISTS telemetry (
    event_id UUID PRIMARY KEY,
    device_id VARCHAR(128) NOT NULL,
    sensor_type VARCHAR(32) NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit VARCHAR(24) NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    baseline_processed BOOLEAN NOT NULL DEFAULT false
);

ALTER TABLE telemetry
    ADD COLUMN IF NOT EXISTS baseline_processed BOOLEAN NOT NULL DEFAULT false;

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

CREATE TABLE IF NOT EXISTS device_baselines (
    device_id VARCHAR(128) NOT NULL,
    sensor_type VARCHAR(32) NOT NULL,
    sample_count BIGINT NOT NULL DEFAULT 0,
    mean DOUBLE PRECISION NOT NULL DEFAULT 0,
    m2 DOUBLE PRECISION NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (device_id, sensor_type)
);

CREATE TABLE IF NOT EXISTS security_events (
    event_id UUID PRIMARY KEY,
    telemetry_event_id UUID NOT NULL REFERENCES telemetry(event_id),
    device_id VARCHAR(128) NOT NULL,
    sensor_type VARCHAR(32) NOT NULL,
    severity VARCHAR(16) NOT NULL,
    anomaly_score DOUBLE PRECISION NOT NULL,
    observed_value DOUBLE PRECISION NOT NULL,
    baseline_mean DOUBLE PRECISION NOT NULL,
    baseline_stddev DOUBLE PRECISION NOT NULL,
    reason TEXT NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS security_events_device_detected_idx
    ON security_events (device_id, detected_at DESC);
CREATE INDEX IF NOT EXISTS security_events_severity_detected_idx
    ON security_events (severity, detected_at DESC);
