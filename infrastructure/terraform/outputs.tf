# ─── Networking ──────────────────────────────────────────────────────────────

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "Public subnet IDs (for ALB)"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "Private subnet IDs (for ECS, RDS)"
  value       = aws_subnet.private[*].id
}

# ─── Load Balancer ────────────────────────────────────────────────────────────

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "alb_arn" {
  description = "ARN of the Application Load Balancer"
  value       = aws_lb.main.arn
}

output "app_url" {
  description = "Application URL (HTTPS if cert provided, HTTP otherwise)"
  value = (
    var.domain_name != "" && local.has_certificate
    ? "https://${var.domain_name}"
    : local.has_certificate
    ? "https://${aws_lb.main.dns_name}"
    : "http://${aws_lb.main.dns_name}"
  )
}

# ─── ECR ──────────────────────────────────────────────────────────────────────

output "ecr_backend_url" {
  description = "ECR repository URL for backend Docker images"
  value       = aws_ecr_repository.backend.repository_url
}

output "ecr_frontend_url" {
  description = "ECR repository URL for frontend Docker images"
  value       = aws_ecr_repository.frontend.repository_url
}

output "ecr_registry" {
  description = "ECR registry URL (without repository name)"
  value       = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com"
}

# ─── S3 ──────────────────────────────────────────────────────────────────────

output "s3_bucket_name" {
  description = "S3 bucket name for project artifacts"
  value       = aws_s3_bucket.artifacts.bucket
}

output "s3_bucket_arn" {
  description = "S3 bucket ARN for project artifacts"
  value       = aws_s3_bucket.artifacts.arn
}

# ─── ECS ──────────────────────────────────────────────────────────────────────

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "ecs_cluster_arn" {
  description = "ECS cluster ARN"
  value       = aws_ecs_cluster.main.arn
}

output "backend_service_name" {
  description = "Backend ECS service name"
  value       = aws_ecs_service.backend.name
}

output "frontend_service_name" {
  description = "Frontend ECS service name"
  value       = aws_ecs_service.frontend.name
}

# ─── Database ────────────────────────────────────────────────────────────────

output "db_endpoint" {
  description = "RDS PostgreSQL endpoint address"
  value       = aws_db_instance.postgres.address
  sensitive   = true
}

output "db_port" {
  description = "RDS PostgreSQL port"
  value       = aws_db_instance.postgres.port
}

output "db_async_url_secret_arn" {
  description = "Secrets Manager ARN for the asyncpg DATABASE_URL"
  value       = aws_secretsmanager_secret.db_async_url.arn
}

output "db_sync_url_secret_arn" {
  description = "Secrets Manager ARN for the psycopg DATABASE_SYNC_URL"
  value       = aws_secretsmanager_secret.db_sync_url.arn
}

# ─── Redis ────────────────────────────────────────────────────────────────────

output "redis_endpoint" {
  description = "ElastiCache Redis primary endpoint"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
  sensitive   = true
}

output "redis_url_secret_arn" {
  description = "Secrets Manager ARN for the Redis connection URL"
  value       = aws_secretsmanager_secret.redis_url.arn
}

# ─── IAM ──────────────────────────────────────────────────────────────────────

output "github_actions_role_arn" {
  description = "IAM Role ARN for GitHub Actions OIDC authentication"
  value       = aws_iam_role.github_actions.arn
}

output "ecs_execution_role_arn" {
  description = "ECS task execution role ARN"
  value       = aws_iam_role.ecs_execution.arn
}

output "ecs_task_role_arn" {
  description = "ECS task role ARN"
  value       = aws_iam_role.ecs_task.arn
}

output "github_oidc_provider_arn" {
  description = "GitHub Actions OIDC provider ARN"
  value       = aws_iam_openid_connect_provider.github_actions.arn
}

# ─── Security Groups ──────────────────────────────────────────────────────────

output "backend_security_group_id" {
  description = "Backend ECS security group ID (needed for Alembic migration tasks)"
  value       = aws_security_group.backend.id
}

# ─── SES ──────────────────────────────────────────────────────────────────────

output "ses_domain_identity" {
  description = "SES domain identity (if configured)"
  value       = var.ses_domain != "" ? aws_ses_domain_identity.main[0].domain : null
}

output "ses_from_email" {
  description = "Email address configured for sending (domain or individual email)"
  value       = var.ses_from_email != "" ? var.ses_from_email : (var.ses_domain != "" ? "noreply@${var.ses_domain}" : null)
}

output "ses_configuration_set_name" {
  description = "SES configuration set name for tracking and metrics"
  value       = aws_ses_configuration_set.main.name
}

output "ses_email_verification_template" {
  description = "SES template name for email verification"
  value       = aws_ses_template.email_verification.name
}

output "ses_password_reset_template" {
  description = "SES template name for password reset"
  value       = aws_ses_template.password_reset.name
}

output "ses_config_secret_arn" {
  description = "Secrets Manager ARN for SES configuration"
  value       = aws_secretsmanager_secret.ses_config.arn
}

output "ses_cloudwatch_log_group" {
  description = "CloudWatch log group for SES events"
  value       = aws_cloudwatch_log_group.ses.name
}

# ─── Account Info ─────────────────────────────────────────────────────────────

output "aws_account_id" {
  description = "AWS account ID"
  value       = data.aws_caller_identity.current.account_id
}

output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}

output "name_prefix" {
  description = "Resource name prefix used throughout this deployment"
  value       = local.name_prefix
}
