# ─── AWS SES Configuration ────────────────────────────────────────────────────
# Simple Email Service for sending transactional emails (verification, notifications)

# ─── SES Domain Identity ──────────────────────────────────────────────────────

resource "aws_ses_domain_identity" "main" {
  count  = var.ses_domain != "" ? 1 : 0
  domain = var.ses_domain
}

resource "aws_ses_domain_dkim" "main" {
  count  = var.ses_domain != "" ? 1 : 0
  domain = aws_ses_domain_identity.main[0].domain
}

resource "aws_ses_domain_mail_from" "main" {
  count            = var.ses_domain != "" && var.ses_mail_from_domain != "" ? 1 : 0
  domain           = aws_ses_domain_identity.main[0].domain
  mail_from_domain = var.ses_mail_from_domain
}

# ─── SES Email Identity (for individual email addresses) ──────────────────────

resource "aws_ses_email_identity" "from_email" {
  count = var.ses_from_email != "" ? 1 : 0
  email = var.ses_from_email
}

# ─── SES Configuration Set ────────────────────────────────────────────────────

resource "aws_ses_configuration_set" "main" {
  name = "${local.name_prefix}-ses-config"

  # Enable open and click tracking for monitoring
  delivery_options {
    tls_policy = "Require"
  }

  # Enable bounce and complaint handling
  reputation_metrics_enabled = true

  tags = {
    Name        = "${local.name_prefix}-ses-config"
    Purpose     = "Email tracking and metrics"
  }
}

# Event destination for bounce/complaint handling
resource "aws_ses_event_destination" "cloudwatch" {
  name                   = "${local.name_prefix}-ses-events"
  configuration_set_name = aws_ses_configuration_set.main.name
  enabled                = true

  matching_types = [
    "bounce",
    "complaint",
    "delivery",
    "reject",
    "send"
  ]

  cloudwatch_destination {
    default_value  = "0"
    dimension_name = "MessageTag"
    value_source   = "messageTag"
  }
}

# ─── SES Identity Policies ────────────────────────────────────────────────────

# Policy for domain identity (if using domain)
resource "aws_ses_identity_policy" "domain_policy" {
  count    = var.ses_domain != "" ? 1 : 0
  identity = aws_ses_domain_identity.main[0].domain
  name     = "${local.name_prefix}-ses-domain-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowSendingEmails"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.ecs_task.arn
        }
        Action = [
          "ses:SendEmail",
          "ses:SendRawEmail"
        ]
        Resource = "*"
      }
    ]
  })
}

# Policy for email identity (if using individual email)
resource "aws_ses_identity_policy" "email_policy" {
  count    = var.ses_from_email != "" ? 1 : 0
  identity = aws_ses_email_identity.from_email[0].email
  name     = "${local.name_prefix}-ses-email-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowSendingEmails"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.ecs_task.arn
        }
        Action = [
          "ses:SendEmail",
          "ses:SendRawEmail"
        ]
        Resource = "*"
      }
    ]
  })
}

# ─── SES Templates ────────────────────────────────────────────────────────────

resource "aws_ses_template" "email_verification" {
  name    = "${local.name_prefix}-email-verification"
  subject = "Verify your AgentForge email address"

  html = templatefile("${path.module}/templates/email_verification.html", {
    app_name = var.project_name
  })

  text = templatefile("${path.module}/templates/email_verification.txt", {
    app_name = var.project_name
  })
}

resource "aws_ses_template" "password_reset" {
  name    = "${local.name_prefix}-password-reset"
  subject = "Reset your AgentForge password"

  html = templatefile("${path.module}/templates/password_reset.html", {
    app_name = var.project_name
  })

  text = templatefile("${path.module}/templates/password_reset.txt", {
    app_name = var.project_name
  })
}

# ─── SES Secrets Manager Integration ──────────────────────────────────────────

# Store SES configuration in Secrets Manager for the backend to use
resource "aws_secretsmanager_secret" "ses_config" {
  name                    = "${local.name_prefix}-ses-config"
  description             = "SES configuration for sending emails"
  recovery_window_in_days = var.environment == "prod" ? 30 : 0

  tags = {
    Name        = "${local.name_prefix}-ses-config"
    Purpose     = "Email service configuration"
  }
}

resource "aws_secretsmanager_secret_version" "ses_config" {
  secret_id = aws_secretsmanager_secret.ses_config.id

  secret_string = jsonencode({
    aws_region           = var.aws_region
    ses_from_email       = var.ses_from_email != "" ? var.ses_from_email : "${var.ses_from_name} <noreply@${var.ses_domain}>"
    ses_from_name        = var.ses_from_name
    ses_configuration_set = aws_ses_configuration_set.main.name
    ses_domain           = var.ses_domain
    templates = {
      email_verification = aws_ses_template.email_verification.name
      password_reset     = aws_ses_template.password_reset.name
    }
  })

  depends_on = [
    aws_ses_domain_identity.main,
    aws_ses_email_identity.from_email,
    aws_ses_template.email_verification,
    aws_ses_template.password_reset
  ]
}

# ─── CloudWatch Monitoring ────────────────────────────────────────────────────

# CloudWatch log group for SES events
resource "aws_cloudwatch_log_group" "ses" {
  name              = "/aws/ses/${local.name_prefix}"
  retention_in_days = var.environment == "prod" ? 30 : 7

  tags = {
    Name        = "${local.name_prefix}-ses-logs"
    Purpose     = "SES email events and metrics"
  }
}

# CloudWatch dashboard for email metrics
resource "aws_cloudwatch_dashboard" "ses" {
  count          = var.enable_ses_monitoring ? 1 : 0
  dashboard_name = "${local.name_prefix}-ses-metrics"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/SES", "Send"],
            [".", "Bounce"],
            [".", "Complaint"],
            [".", "Delivery"],
            [".", "Reject"]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "SES Email Metrics"
        }
      }
    ]
  })
}

# ─── SES Reputation Monitoring ────────────────────────────────────────────────

# CloudWatch alarms for high bounce/complaint rates
resource "aws_cloudwatch_metric_alarm" "ses_bounce_rate" {
  count               = var.enable_ses_monitoring ? 1 : 0
  alarm_name          = "${local.name_prefix}-ses-high-bounce-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Bounce"
  namespace           = "AWS/SES"
  period              = "300"
  statistic           = "Average"
  threshold           = "0.05"  # 5% bounce rate threshold
  alarm_description   = "This metric monitors SES bounce rate"
  alarm_actions       = var.ses_alarm_topic_arn != "" ? [var.ses_alarm_topic_arn] : []

  tags = {
    Name = "${local.name_prefix}-ses-bounce-alarm"
  }
}

resource "aws_cloudwatch_metric_alarm" "ses_complaint_rate" {
  count               = var.enable_ses_monitoring ? 1 : 0
  alarm_name          = "${local.name_prefix}-ses-high-complaint-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Complaint"
  namespace           = "AWS/SES"
  period              = "300"
  statistic           = "Average"
  threshold           = "0.001"  # 0.1% complaint rate threshold
  alarm_description   = "This metric monitors SES complaint rate"
  alarm_actions       = var.ses_alarm_topic_arn != "" ? [var.ses_alarm_topic_arn] : []

  tags = {
    Name = "${local.name_prefix}-ses-complaint-alarm"
  }
}