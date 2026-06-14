# EMR cluster + daily-SLA Spark step for the transcript ETL.
# This is the production target for `optimized_etl.py`. Local runs use `local[*]`.

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

variable "region" { default = "us-east-1" }
variable "release_label" { default = "emr-7.1.0" }
variable "log_bucket" { type = string }
variable "code_bucket" { type = string }
variable "subnet_id" { type = string }

resource "aws_emr_cluster" "transcript_etl" {
  name          = "transcript-intelligence-etl"
  release_label = var.release_label
  applications  = ["Spark"]

  ec2_attributes {
    subnet_id        = var.subnet_id
    instance_profile = aws_iam_instance_profile.emr_profile.arn
  }

  master_instance_group {
    instance_type  = "m5.xlarge"
    instance_count = 1
  }

  core_instance_group {
    instance_type  = "m5.2xlarge"
    instance_count = 4

    # Auto-scaling supports the multi-tenant daily SLA across 100+ tenant partitions.
    autoscaling_policy = jsonencode({
      Constraints = { MinCapacity = 4, MaxCapacity = 20 }
      Rules = [{
        Name = "scale-out-on-yarn-pending"
        Action = { SimpleScalingPolicyConfiguration = {
          AdjustmentType = "CHANGE_IN_CAPACITY", ScalingAdjustment = 2, CoolDown = 300
        } }
        Trigger = { CloudWatchAlarmDefinition = {
          ComparisonOperator = "GREATER_THAN", EvaluationPeriods = 1,
          MetricName = "YARNMemoryAvailablePercentage", Period = 300,
          Threshold = 15, Statistic = "AVERAGE", Unit = "PERCENT"
        } }
      }]
    })
  }

  # Spark defaults baked with the partition-tuning / skew-handling config from common.py.
  configurations_json = jsonencode([
    {
      Classification = "spark-defaults",
      Properties = {
        "spark.sql.adaptive.enabled"                  = "true"
        "spark.sql.adaptive.skewJoin.enabled"         = "true"
        "spark.sql.adaptive.coalescePartitions.enabled" = "true"
        "spark.sql.shuffle.partitions"                = "400"
        "spark.serializer"                            = "org.apache.spark.serializer.KryoSerializer"
        "spark.dynamicAllocation.enabled"             = "true"
      }
    }
  ])

  log_uri = "s3://${var.log_bucket}/emr/"

  step {
    name              = "daily-transcript-etl"
    action_on_failure = "CONTINUE"
    hadoop_jar_step {
      jar  = "command-runner.jar"
      args = [
        "spark-submit", "--deploy-mode", "cluster",
        "s3://${var.code_bucket}/jobs/optimized_etl.py",
        "--rows", "0", "--strategy", "salt"
      ]
    }
  }

  service_role = aws_iam_role.emr_service.arn
  tags         = { Project = "transcript-intelligence-platform", Pillar = "etl" }
}

# (IAM roles abbreviated for brevity; see infra/iam.tf in a real deployment.)
resource "aws_iam_role" "emr_service" {
  name               = "transcript-etl-emr-service"
  assume_role_policy = data.aws_iam_policy_document.emr_assume.json
}

resource "aws_iam_role" "emr_ec2" {
  name               = "transcript-etl-emr-ec2"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_instance_profile" "emr_profile" {
  name = "transcript-etl-emr-profile"
  role = aws_iam_role.emr_ec2.name
}

data "aws_iam_policy_document" "emr_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["elasticmapreduce.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}
