variable "aws_region" {
  type        = string
  description = "AWS region to deploy into"
  default     = "us-east-1"
}

variable "project_name" {
  type        = string
  description = "Prefix used for resource names"
  default     = "iot-telemetry"
}

variable "db_instance_class" {
  type        = string
  description = "RDS PostgreSQL instance class"
  default     = "db.t4g.micro"
}

variable "lambda_zip" {
  type        = string
  description = "Path to the Lambda deployment zip"
  default     = "../dist/lambda.zip"
}
