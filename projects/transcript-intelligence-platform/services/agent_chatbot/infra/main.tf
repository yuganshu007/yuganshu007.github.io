# Serverless deployment for the transcript agent: Lambda behind API Gateway, calling Bedrock
# Claude 3.5 Haiku. IAM scoped to a single model id.

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" { region = var.region }

variable "region" { default = "us-east-1" }
variable "model_id" { default = "anthropic.claude-3-5-haiku-20241022-v1:0" }
variable "code_s3_key" { type = string }
variable "code_bucket" { type = string }

resource "aws_iam_role" "agent" {
  name               = "transcript-agent-lambda"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "bedrock" {
  statement {
    sid       = "InvokeClaudeHaiku"
    actions   = ["bedrock:InvokeModel", "bedrock:Converse"]
    resources = ["arn:aws:bedrock:${var.region}::foundation-model/${var.model_id}"]
  }
}

resource "aws_iam_role_policy" "bedrock" {
  role   = aws_iam_role.agent.id
  policy = data.aws_iam_policy_document.bedrock.json
}

resource "aws_lambda_function" "agent" {
  function_name = "transcript-agent"
  role          = aws_iam_role.agent.arn
  runtime       = "python3.12"
  handler       = "services.agent_chatbot.app.lambda_handler.handler"
  s3_bucket     = var.code_bucket
  s3_key        = var.code_s3_key
  timeout       = 30
  memory_size   = 512

  environment {
    variables = {
      LLM_BACKEND      = "bedrock"
      BEDROCK_MODEL_ID = var.model_id
      AGENT_P95_BUDGET_S = "2.0"
      LOG_LEVEL        = "INFO"
    }
  }
}

resource "aws_apigatewayv2_api" "agent" {
  name          = "transcript-agent-api"
  protocol_type = "HTTP"
}
