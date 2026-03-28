# ─── DB Subnet Group ──────────────────────────────────────────────────────────

resource "aws_db_subnet_group" "main" {
  name       = "${local.name_prefix}-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id

  tags = { Name = "${local.name_prefix}-db-subnet-group" }
}

# ─── DB Parameter Group ───────────────────────────────────────────────────────

resource "aws_db_parameter_group" "postgres" {
  name   = "${local.name_prefix}-postgres15"
  family = "postgres15"

  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements"
  }

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"  # Log queries taking > 1 second
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = { Name = "${local.name_prefix}-postgres15" }
}

# ─── RDS PostgreSQL Instance ──────────────────────────────────────────────────

resource "aws_db_instance" "postgres" {
  identifier = "${local.name_prefix}-postgres"

  # Engine
  engine               = "postgres"
  engine_version       = "15.7"
  instance_class       = var.db_instance_class

  # Storage
  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = var.db_max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true

  # Credentials
  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  # Network
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false
  multi_az               = local.is_production

  # Backup
  backup_retention_period   = local.is_production ? 7 : 1
  backup_window             = "03:00-04:00"
  maintenance_window        = "sun:04:00-sun:05:00"
  copy_tags_to_snapshot     = true
  deletion_protection       = local.is_production
  skip_final_snapshot       = !local.is_production
  final_snapshot_identifier = local.is_production ? "${local.name_prefix}-final-${formatdate("YYYYMMDD", timestamp())}" : null

  # Configuration
  parameter_group_name       = aws_db_parameter_group.postgres.name
  auto_minor_version_upgrade = true

  # Monitoring
  enabled_cloudwatch_logs_exports       = ["postgresql", "upgrade"]
  monitoring_interval                   = 60
  monitoring_role_arn                   = aws_iam_role.rds_monitoring.arn
  performance_insights_enabled          = true
  performance_insights_retention_period = local.is_production ? 31 : 7

  tags = { Name = "${local.name_prefix}-postgres" }
}

# ─── RDS Enhanced Monitoring Role ────────────────────────────────────────────

resource "aws_iam_role" "rds_monitoring" {
  name = "${local.name_prefix}-rds-monitoring"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "monitoring.rds.amazonaws.com" }
    }]
  })

  tags = { Name = "${local.name_prefix}-rds-monitoring" }
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# ─── Secrets Manager: Individual URL Secrets ─────────────────────────────────
#
# Store each URL as a separate secret so ECS task definitions can reference
# them directly without the JSON-key path syntax (which requires extra IAM).

resource "aws_secretsmanager_secret" "db_async_url" {
  name                    = "${local.name_prefix}/db-async-url"
  description             = "PostgreSQL asyncpg connection URL for FastAPI"
  recovery_window_in_days = local.is_production ? 7 : 0

  tags = { Name = "${local.name_prefix}-db-async-url" }
}

resource "aws_secretsmanager_secret_version" "db_async_url" {
  secret_id = aws_secretsmanager_secret.db_async_url.id
  secret_string = "postgresql+asyncpg://${var.db_username}:${var.db_password}@${aws_db_instance.postgres.address}:5432/${var.db_name}"
}

resource "aws_secretsmanager_secret" "db_sync_url" {
  name                    = "${local.name_prefix}/db-sync-url"
  description             = "PostgreSQL psycopg (sync) connection URL for Alembic and LangGraph checkpointer"
  recovery_window_in_days = local.is_production ? 7 : 0

  tags = { Name = "${local.name_prefix}-db-sync-url" }
}

resource "aws_secretsmanager_secret_version" "db_sync_url" {
  secret_id = aws_secretsmanager_secret.db_sync_url.id
  secret_string = "postgresql+psycopg://${var.db_username}:${var.db_password}@${aws_db_instance.postgres.address}:5432/${var.db_name}"
}

# Combined JSON secret kept for operational convenience (not used by ECS)
resource "aws_secretsmanager_secret" "db_credentials" {
  name                    = "${local.name_prefix}/db-credentials"
  description             = "Full DB credentials JSON (operational reference)"
  recovery_window_in_days = local.is_production ? 7 : 0

  tags = { Name = "${local.name_prefix}-db-credentials" }
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    host     = aws_db_instance.postgres.address
    port     = aws_db_instance.postgres.port
    name     = var.db_name
    username = var.db_username
    password = var.db_password
  })
}
