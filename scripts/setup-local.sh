#!/usr/bin/env bash
set -euo pipefail

# ─── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERR]${NC}  $*"; exit 1; }

# ─── Prerequisites ────────────────────────────────────────────────────────────

info "Checking prerequisites..."

command -v docker  >/dev/null 2>&1 || error "Docker is required. Install: https://docs.docker.com/get-docker/"
command -v python3 >/dev/null 2>&1 || error "Python 3.11+ is required."
command -v node    >/dev/null 2>&1 || error "Node.js 20+ is required."
command -v npm     >/dev/null 2>&1 || error "npm is required."
command -v aws     >/dev/null 2>&1 || warn  "AWS CLI not found — infrastructure deployment will not work."

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
NODE_VERSION=$(node --version | sed 's/v//')

info "Python: $PYTHON_VERSION"
info "Node:   $NODE_VERSION"

# ─── Environment Files ────────────────────────────────────────────────────────

info "Setting up environment files..."

if [ ! -f .env ]; then
  cp .env.example .env
  warn "Created .env from .env.example — update with your AWS credentials"
fi

if [ ! -f backend/.env ]; then
  cp .env.example backend/.env
  info "Created backend/.env"
fi

# ─── Python Virtual Environment ───────────────────────────────────────────────

info "Setting up Python virtual environment..."

cd backend

if [ ! -d .venv ]; then
  python3 -m venv .venv
  success "Created .venv"
fi

# shellcheck source=/dev/null
source .venv/bin/activate

pip install --upgrade pip --quiet
pip install -r requirements-dev.txt --quiet
success "Backend Python dependencies installed"

cd ..

# ─── Frontend Dependencies ────────────────────────────────────────────────────

info "Installing frontend dependencies..."
cd frontend
npm ci --silent
success "Frontend npm dependencies installed"
cd ..

# ─── Docker Infrastructure ────────────────────────────────────────────────────

info "Starting Docker infrastructure (postgres, redis)..."

docker compose up -d postgres postgres_test redis

# Wait for primary postgres
info "Waiting for PostgreSQL to be ready..."
RETRIES=30
until docker compose exec -T postgres pg_isready -U agentforge -d agentforge > /dev/null 2>&1; do
  RETRIES=$((RETRIES - 1))
  if [ $RETRIES -eq 0 ]; then
    error "PostgreSQL did not become ready in time"
  fi
  sleep 1
done
success "PostgreSQL is ready"

# Wait for test postgres
info "Waiting for test PostgreSQL to be ready..."
RETRIES=30
until docker compose exec -T postgres_test pg_isready -U agentforge -d agentforge_test > /dev/null 2>&1; do
  RETRIES=$((RETRIES - 1))
  if [ $RETRIES -eq 0 ]; then
    warn "Test PostgreSQL did not become ready — tests may fail"
    break
  fi
  sleep 1
done
success "Test PostgreSQL is ready"

# Wait for redis
info "Waiting for Redis to be ready..."
RETRIES=10
until docker compose exec -T redis redis-cli ping > /dev/null 2>&1; do
  RETRIES=$((RETRIES - 1))
  if [ $RETRIES -eq 0 ]; then
    error "Redis did not become ready in time"
  fi
  sleep 1
done
success "Redis is ready"

# ─── Database Migrations ──────────────────────────────────────────────────────

info "Running database migrations..."
cd backend
source .venv/bin/activate

# Run migrations on the main database
alembic upgrade head
success "Main database migrations applied"

# Run migrations on the test database
DATABASE_SYNC_URL="postgresql+psycopg://agentforge:password@localhost:5433/agentforge_test" \
  alembic upgrade head
success "Test database migrations applied"

cd ..

# ─── Verify AWS Bedrock Access (optional) ────────────────────────────────────

if command -v aws >/dev/null 2>&1 && [ -n "${AWS_ACCESS_KEY_ID:-}" ]; then
  info "Checking AWS Bedrock model access..."
  MODELS=$(aws bedrock list-foundation-models \
    --region "${AWS_REGION:-us-east-1}" \
    --query 'modelSummaries[?contains(modelId,`claude-3-5`)].modelId' \
    --output text 2>/dev/null || echo "")

  if echo "$MODELS" | grep -q "claude-3-5-sonnet"; then
    success "Claude 3.5 Sonnet access verified"
  else
    warn "Claude 3.5 Sonnet not found — enable in AWS Console → Bedrock → Model Access"
  fi
else
  warn "AWS credentials not set — skipping Bedrock check"
  warn "Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env before running"
fi

# ─── Success Summary ──────────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}  AgentForge local setup complete! 🚀   ${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo ""
echo "Start the application:"
echo ""
echo "  Option A — Docker Compose (recommended):"
echo "    docker compose up"
echo ""
echo "  Option B — Development servers:"
echo "    Backend:  cd backend && source .venv/bin/activate && uvicorn app.main:app --reload"
echo "    Frontend: cd frontend && npm run dev"
echo ""
echo "  URLs:"
echo "    Frontend:  http://localhost:5173"
echo "    API:       http://localhost:8000"
echo "    API Docs:  http://localhost:8000/api/v1/docs"
echo ""
echo "Run tests:"
echo "    make test"
echo ""
