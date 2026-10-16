from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "IoT Telemetry Pipeline"
    environment: str = "development"
    aws_region: str = "us-east-1"
    firehose_stream_name: str = "iot-telemetry"
    telemetry_bucket: str | None = None
    database_url: str = "postgresql://iot:iot@localhost:5432/iot"
    local_processing: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
