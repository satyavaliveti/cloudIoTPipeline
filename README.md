# Cloud IoT Telemetry Pipeline

A production-oriented, cloud-native ETL service for real-time sensor telemetry. FastAPI validates incoming events and publishes them to Amazon Data Firehose. A Lambda processor cleans each event, calculates hourly aggregates, persists queryable data in PostgreSQL, and returns newline-delimited JSON to Firehose for durable storage in Amazon S3.

## Architecture

```text
Devices -> API Gateway -> FastAPI Lambda -> Data Firehose
                                             |
                                      Transform Lambda
                                       /           \
                              PostgreSQL RDS       Amazon S3
                              raw + hourly         partitioned gzip
```

The stack includes:

- Single-event and batch ingestion (up to 500 events)
- Pydantic schema validation and physical-range outlier rejection
- UTC timestamp normalization and unit cleanup
- Idempotent PostgreSQL writes and hourly device/sensor aggregates
- Date-partitioned, encrypted S3 storage with lifecycle transition
- Private RDS, VPC-attached Lambdas, and a Firehose VPC endpoint
- Local Docker Compose environment and pytest coverage
- Terraform for API Gateway, Lambda, Firehose, S3, RDS, IAM, and networking

## Run locally

```powershell
docker compose up --build
```

Open `http://localhost:8000/docs`, or send an event:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/v1/telemetry `
  -ContentType "application/json" `
  -Body '{"device_id":"factory-1","sensor_type":"temperature","value":23.4,"unit":"c","recorded_at":"2026-10-15T19:00:00Z"}'
```

Local mode writes validated telemetry directly to PostgreSQL. Query recent rows with:

```powershell
Invoke-RestMethod http://localhost:8000/v1/telemetry?device_id=factory-1
```

## Develop and test

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
ruff check .
```

## Deploy to AWS

AWS credentials, Terraform 1.7+, and Python 3.11+ are required.

```powershell
.\scripts\build_lambda.ps1
cd infra
terraform init
terraform plan -out deploy.tfplan
terraform apply deploy.tfplan
terraform output api_url
```

Terraform uses the account's default VPC and creates billable AWS resources, including RDS and interface VPC endpoints. The generated database password is stored as sensitive Terraform state; use an encrypted remote state backend for shared environments.

For API clients, set the event fields `device_id`, `sensor_type`, `value`, `unit`, and optionally `recorded_at` and `metadata`. Supported sensor types are `temperature`, `humidity`, `pressure`, `air_quality`, and `vibration`.

## Configuration

Copy `.env.example` to `.env` for direct Python execution. `LOCAL_PROCESSING=true` bypasses Firehose and writes directly to PostgreSQL; deployed environments leave it false. API documentation is exposed at `/docs`, health at `/health`, ingestion at `/v1/telemetry`, and batch ingestion at `/v1/telemetry/batch`.
