#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT=${1:-prod}
AWS_REGION=${AWS_REGION:-us-east-1}
PROJECT_NAME=${PROJECT_NAME:-agentforge}
IMAGE_TAG=${IMAGE_TAG:-$(git rev-parse --short HEAD 2>/dev/null || echo "latest")}

echo "🐳 Building and pushing Docker images..."
echo "   Environment: $ENVIRONMENT"
echo "   Region:      $AWS_REGION"
echo "   Image Tag:   $IMAGE_TAG"

# ─── Get AWS Account ID ───────────────────────────────────────────────────────

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_BASE="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

BACKEND_REPO="${ECR_BASE}/${PROJECT_NAME}-${ENVIRONMENT}-backend"
FRONTEND_REPO="${ECR_BASE}/${PROJECT_NAME}-${ENVIRONMENT}-frontend"

echo "   Backend:  $BACKEND_REPO"
echo "   Frontend: $FRONTEND_REPO"

# ─── Authenticate with ECR ────────────────────────────────────────────────────

echo "🔑 Authenticating with ECR..."
aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin "$ECR_BASE"

# ─── Build Backend ────────────────────────────────────────────────────────────

echo "🔨 Building backend image..."
docker build \
  --platform linux/amd64 \
  --file ./backend/Dockerfile \
  --tag "${BACKEND_REPO}:${IMAGE_TAG}" \
  --tag "${BACKEND_REPO}:latest" \
  --build-arg BUILDKIT_INLINE_CACHE=1 \
  --cache-from "${BACKEND_REPO}:latest" \
  ./backend/

echo "📤 Pushing backend image..."
docker push "${BACKEND_REPO}:${IMAGE_TAG}"
docker push "${BACKEND_REPO}:latest"

# ─── Build Frontend ───────────────────────────────────────────────────────────

# Resolve API URLs
VITE_API_URL=${VITE_API_URL:-"https://$(
  cd infrastructure/terraform && \
  terraform output -raw alb_dns_name 2>/dev/null || echo "localhost:8000"
)"}
VITE_WS_URL=${VITE_WS_URL:-${VITE_API_URL/https:/wss:}}

echo "🔨 Building frontend image..."
echo "   VITE_API_URL: $VITE_API_URL"
echo "   VITE_WS_URL:  $VITE_WS_URL"

docker build \
  --platform linux/amd64 \
  --file ./frontend/Dockerfile \
  --tag "${FRONTEND_REPO}:${IMAGE_TAG}" \
  --tag "${FRONTEND_REPO}:latest" \
  --build-arg VITE_API_URL="${VITE_API_URL}" \
  --build-arg VITE_WS_URL="${VITE_WS_URL}" \
  --build-arg BUILDKIT_INLINE_CACHE=1 \
  --cache-from "${FRONTEND_REPO}:latest" \
  ./frontend/

echo "📤 Pushing frontend image..."
docker push "${FRONTEND_REPO}:${IMAGE_TAG}"
docker push "${FRONTEND_REPO}:latest"

echo ""
echo "✅ Images pushed successfully!"
echo ""
echo "  Backend:  ${BACKEND_REPO}:${IMAGE_TAG}"
echo "  Frontend: ${FRONTEND_REPO}:${IMAGE_TAG}"
echo ""
echo "Update ECS services with:"
echo "  aws ecs update-service --cluster ${PROJECT_NAME}-${ENVIRONMENT}-cluster \"
echo "    --service ${PROJECT_NAME}-${ENVIRONMENT}-backend --force-new-deployment"
echo "  aws ecs update-service --cluster ${PROJECT_NAME}-${ENVIRONMENT}-cluster \"
echo "    --service ${PROJECT_NAME}-${ENVIRONMENT}-frontend --force-new-deployment"
