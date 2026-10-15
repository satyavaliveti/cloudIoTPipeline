output "firehose_stream_name" {
  value = aws_kinesis_firehose_delivery_stream.telemetry.name
}

output "api_url" {
  value = aws_apigatewayv2_api.api.api_endpoint
}

output "s3_bucket" {
  value = aws_s3_bucket.telemetry.id
}

output "database_endpoint" {
  value = aws_db_instance.postgres.endpoint
}

output "database_password" {
  value     = random_password.db.result
  sensitive = true
}
