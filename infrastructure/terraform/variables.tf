variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "prod"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "agentforge"
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones to use"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

# ─── Database ─────────────────────────────────────────────────────────────────

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "db_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "agentforge"
}

variable "db_username" {
  description = "PostgreSQL master username"
  type        = string
  default     = "agentforge"
}

variable "db_password" {
  description = "PostgreSQL master password (sensitive)"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.db_password) >= 16
    error_message = "Database password must be at least 16 characters."
  }
}

variable "db_allocated_storage" {
  description = "Initial RDS storage in GB"
  type        = number
  default     = 20
}

variable "db_max_allocated_storage" {
  description = "Maximum RDS auto-scaling storage in GB"
  type        = number
  default     = 100
}

# ─── Redis ────────────────────────────────────────────────────────────────────

variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.micro"
}

# ─── ECS ─────────────────────────────────────────────────────────────────────

variable "backend_cpu" {
  description = "Backend ECS task CPU units (256, 512, 1024, 2048, 4096)"
  type        = number
  default     = 512
}

variable "backend_memory" {
  description = "Backend ECS task memory in MB"
  type        = number
  default     = 1024
}

variable "frontend_cpu" {
  description = "Frontend ECS task CPU units"
  type        = number
  default     = 256
}

variable "frontend_memory" {
  description = "Frontend ECS task memory in MB"
  type        = number
  default     = 512
}

variable "backend_desired_count" {
  description = "Desired number of backend ECS tasks"
  type        = number
  default     = 2
}

variable "frontend_desired_count" {
  description = "Desired number of frontend ECS tasks"
  type        = number
  default     = 2
}

variable "backend_min_capacity" {
  description = "Minimum number of backend tasks for auto-scaling"
  type        = number
  default     = 2
}

variable "backend_max_capacity" {
  description = "Maximum number of backend tasks for auto-scaling"
  type        = number
  default     = 10
}

# ─── HTTPS / TLS ──────────────────────────────────────────────────────────────

variable "domain_name" {
  description = "Custom domain name (optional; leave empty to use ALB DNS)"
  type        = string
  default     = ""
}

variable "certificate_arn" {
  description = "ACM certificate ARN for HTTPS (optional; leave empty for HTTP-only)"
  type        = string
  default     = ""
}

# ─── Application ──────────────────────────────────────────────────────────────

variable "bedrock_model_id" {
  description = "AWS Bedrock model ID for the primary (slower, smarter) model"
  type        = string
  default     = "anthropic.claude-3-5-sonnet-20241022-v2:0"
}

variable "bedrock_fast_model_id" {
  description = "AWS Bedrock model ID for the fast (cheaper) model"
  type        = string
  default     = "anthropic.claude-3-5-haiku-20241022-v1:0"
}

variable "secret_key" {
  description = "Application secret key for JWT signing (minimum 32 characters)"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.secret_key) >= 32
    error_message = "Secret key must be at least 32 characters."
  }
}

variable "cors_origins" {
  description = "Comma-separated CORS allowed origins"
  type        = string
  default     = ""
}

# ─── GitHub Actions ───────────────────────────────────────────────────────────

variable "github_org" {
  description = "GitHub organisation or username for OIDC trust policy"
  type        = string
  default     = "*"
}

variable "github_repo" {
  description = "GitHub repository name for OIDC trust policy (e.g. agentforge)"
  type        = string
  default     = "agentforge"
}

# ─── Email Service (SES) ──────────────────────────────────────────────────────

variable "ses_domain" {
  description = "Domain name for SES email sending (leave empty to use individual email identity)"
  type        = string
  default     = ""
}

variable "ses_from_email" {
  description = "Email address to send emails from (use when not using domain identity)"
  type        = string
  default     = ""
}

variable "ses_from_name" {
  description = "Display name for email sender"
  type        = string
  default     = "AgentForge"
}

variable "ses_mail_from_domain" {
  description = "Custom MAIL FROM domain for SES (optional, improves deliverability)"
  type        = string
  default     = ""
}

variable "enable_ses_monitoring" {
  description = "Enable CloudWatch monitoring and alarms for SES"
  type        = bool
  default     = true
}

variable "ses_alarm_topic_arn" {
  description = "SNS topic ARN for SES alarms (optional)"
  type        = string
  default     = ""
}

# ─── Tagging ──────────────────────────────────────────────────────────────────

variable "additional_tags" {
  description = "Additional resource tags"
  type        = map(string)
  default     = {}
}
