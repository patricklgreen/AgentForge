terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Remote state — configure via -backend-config flags or environment variables.
  # Run: terraform init \
  #   -backend-config="bucket=<your-state-bucket>" \
  #   -backend-config="key=agentforge/${var.environment}/terraform.tfstate" \
  #   -backend-config="region=us-east-1"
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = merge(
      {
        Project     = var.project_name
        Environment = var.environment
        ManagedBy   = "terraform"
        Repository  = "${var.github_org}/${var.github_repo}"
      },
      var.additional_tags
    )
  }
}

# ─── Local Values ─────────────────────────────────────────────────────────────

locals {
  name_prefix = "${var.project_name}-${var.environment}"

  # Convenience booleans
  has_certificate = var.certificate_arn != ""
  is_production   = var.environment == "prod"

  # CORS origins: use explicit value or derive from ALB DNS
  cors_origins = var.cors_origins != "" ? var.cors_origins : (
    local.has_certificate && var.domain_name != ""
    ? "https://${var.domain_name}"
    : "http://${aws_lb.main.dns_name}"
  )
}

# ─── Data Sources ─────────────────────────────────────────────────────────────

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

data "aws_elb_service_account" "main" {}
