# Glue catalog + Athena workgroup for the self-serve analytics layer, plus an ECS Fargate
# service (behind an ALB) hosting the Streamlit app. Auto-scaling supports the adopting teams.

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" { region = var.region }

variable "region" { default = "us-east-1" }
variable "curated_bucket" { type = string }
variable "athena_results_bucket" { type = string }

resource "aws_glue_catalog_database" "ti" {
  name = "transcript_intelligence"
}

resource "aws_glue_crawler" "curated" {
  name          = "transcript-curated-crawler"
  role          = aws_iam_role.glue.arn
  database_name = aws_glue_catalog_database.ti.name
  schedule      = "cron(0 6 * * ? *)" # daily, after the ETL SLA window

  s3_target {
    path = "s3://${var.curated_bucket}/curated/"
  }
  s3_target {
    path = "s3://${var.curated_bucket}/gold/"
  }
}

resource "aws_athena_workgroup" "ti" {
  name = "transcript-intelligence"
  configuration {
    enforce_workgroup_configuration = true
    result_configuration {
      output_location = "s3://${var.athena_results_bucket}/athena/"
    }
    # Cost guard: cap bytes scanned per query (gold table keeps this small).
    bytes_scanned_cutoff_per_query = 10737418240 # 10 GB
  }
}

resource "aws_iam_role" "glue" {
  name               = "transcript-glue-crawler"
  assume_role_policy = data.aws_iam_policy_document.glue_assume.json
}

data "aws_iam_policy_document" "glue_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }
  }
}

resource "aws_appautoscaling_target" "dashboard" {
  max_capacity       = 10
  min_capacity       = 1
  resource_id        = "service/transcript-intelligence/dashboard"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}
