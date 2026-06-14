# CloudWatch alarms for the platform: data-quality, agent latency, and pipeline failures.
# These back the resume bullet's "CloudWatch alarms" + "stabilized end-to-end daily runs".

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" { region = var.region }

variable "region" { default = "us-east-1" }
variable "alarm_topic_arn" { type = string } # SNS topic for paging

resource "aws_cloudwatch_metric_alarm" "data_quality" {
  alarm_name          = "transcript-data-quality-below-999"
  namespace           = "TranscriptIntelligence/DataQuality"
  metric_name         = "PassRatePercent"
  statistic           = "Minimum"
  period              = 300
  evaluation_periods  = 1
  comparison_operator = "LessThanThreshold"
  threshold           = 99.9
  alarm_description   = "Data-quality pass rate dropped below 99.9%."
  alarm_actions       = [var.alarm_topic_arn]
  treat_missing_data  = "breaching"
}

resource "aws_cloudwatch_metric_alarm" "agent_p95" {
  alarm_name          = "transcript-agent-p95-over-2s"
  namespace           = "TranscriptIntelligence/Agent"
  metric_name         = "LatencyP95Seconds"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 3
  comparison_operator = "GreaterThanThreshold"
  threshold           = 2.0
  alarm_description   = "Agent p95 latency exceeded the 2s SLO for 3 minutes."
  alarm_actions       = [var.alarm_topic_arn]
}

resource "aws_cloudwatch_metric_alarm" "etl_failures" {
  alarm_name          = "transcript-etl-daily-failures"
  namespace           = "TranscriptIntelligence/ETL"
  metric_name         = "FailedRuns"
  statistic           = "Sum"
  period              = 3600
  evaluation_periods  = 1
  comparison_operator = "GreaterThanThreshold"
  threshold           = 0
  alarm_description   = "A daily ETL run failed."
  alarm_actions       = [var.alarm_topic_arn]
  treat_missing_data  = "notBreaching"
}
