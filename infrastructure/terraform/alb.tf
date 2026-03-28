# ─── Application Load Balancer ────────────────────────────────────────────────

resource "aws_lb" "main" {
  name               = "${local.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  enable_deletion_protection = local.is_production
  enable_http2               = true
  idle_timeout               = 120  # seconds; longer for WebSocket connections

  access_logs {
    bucket  = aws_s3_bucket.alb_logs.bucket
    prefix  = "alb"
    enabled = true
  }

  depends_on = [aws_s3_bucket_policy.alb_logs]

  tags = { Name = "${local.name_prefix}-alb" }
}

# ─── Target Groups ────────────────────────────────────────────────────────────

resource "aws_lb_target_group" "backend" {
  name        = "${local.name_prefix}-backend-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 10
    interval            = 30
    path                = "/api/v1/health"
    matcher             = "200"
    protocol            = "HTTP"
  }

  deregistration_delay = 30

  stickiness {
    type    = "lb_cookie"
    enabled = false
  }

  tags = { Name = "${local.name_prefix}-backend-tg" }
}

resource "aws_lb_target_group" "frontend" {
  name        = "${local.name_prefix}-frontend-tg"
  port        = 80
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 10
    interval            = 30
    path                = "/health"
    matcher             = "200"
    protocol            = "HTTP"
  }

  deregistration_delay = 30

  tags = { Name = "${local.name_prefix}-frontend-tg" }
}

# ─── Listeners ────────────────────────────────────────────────────────────────
#
# Critical fix: only ONE listener can bind to port 80 at a time.
# When certificate_arn is provided:
#   - Port 80  → redirect to HTTPS 443  (http_redirect)
#   - Port 443 → serve traffic           (https)
# When no certificate:
#   - Port 80  → serve traffic directly  (http_direct)
#
# Exactly one of http_redirect and http_direct is created at any time.

resource "aws_lb_listener" "http_redirect" {
  count             = local.has_certificate ? 1 : 0
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }

  tags = { Name = "${local.name_prefix}-http-redirect" }
}

resource "aws_lb_listener" "http_direct" {
  count             = local.has_certificate ? 0 : 1
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }

  tags = { Name = "${local.name_prefix}-http-direct" }
}

resource "aws_lb_listener" "https" {
  count             = local.has_certificate ? 1 : 0
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }

  tags = { Name = "${local.name_prefix}-https" }
}

# ─── Active Listener ARN (for routing rules) ──────────────────────────────────
#
# This local picks whichever listener is active so routing rules
# reference the correct listener regardless of certificate configuration.

locals {
  active_listener_arn = local.has_certificate ? aws_lb_listener.https[0].arn : aws_lb_listener.http_direct[0].arn
}

# ─── Listener Rules ───────────────────────────────────────────────────────────

# Route /api/* and /ws/* to backend
resource "aws_lb_listener_rule" "api" {
  listener_arn = local.active_listener_arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }

  condition {
    path_pattern {
      values = ["/api/*", "/ws/*"]
    }
  }

  tags = { Name = "${local.name_prefix}-api-rule" }
}
