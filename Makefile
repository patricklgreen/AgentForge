# ─── AgentForge Makefile ──────────────────────────────────────────────────────
# Usage: make   [ENVIRONMENT=dev|prod]
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: help setup dev-up dev-down dev-backend dev-frontend \
        test test-backend test-frontend \
        lint lint-backend lint-frontend \
        format format-backend format-frontend \
        migrate migrate-new \
        build push \
        infra-init infra-plan infra-apply infra-destroy \
        clean logs

# Default environment
ENVIRONMENT ?= dev
AWS_REGION  ?= us-east-1
PROJECT     ?= agentforge

# Detect OS for sed compatibility
UNAME := $(shell uname)
ifeq ($(UNAME), Darwin)
  SED = sed -i ''
else
  SED = sed -i
endif

# ─── Help ─────────────────────────────────────────────────────────────────────

help: ## Show all available make targets
	@echo ""
	@echo "AgentForge — Available Commands"
	@echo "================================"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  sort | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ─── Local Development Setup ──────────────────────────────────────────────────

setup: ## Full local setup (dependencies, DB, migrations)
	@chmod +x scripts/*.sh
	@bash scripts/setup-local.sh

dev-up: ## Start Docker Compose services (postgres, redis, backend, frontend)
	@docker compose up -d
	@echo ""
	@echo "Services started:"
	@echo "  Frontend: http://localhost:5173"
	@echo "  Backend:  http://localhost:8000"
	@echo "  API Docs: http://localhost:8000/api/v1/docs"
	@echo ""

dev-down: ## Stop Docker Compose services
	@docker compose down

dev-clean: ## Stop Docker Compose services and remove volumes
	@docker compose down -v
	@echo "All containers and volumes removed"

dev-backend: ## Run backend with hot reload (requires local .venv)
	@cd backend && \
	  source .venv/bin/activate && \
	  uvicorn app.main:app \
	    --host 0.0.0.0 \
	    --port 8000 \
	    --reload \
	    --reload-dir app

dev-frontend: ## Run frontend dev server
	@cd frontend && npm run dev

logs: ## Tail Docker Compose logs
	@docker compose logs -f

# ─── Testing ──────────────────────────────────────────────────────────────────

test: test-backend test-frontend ## Run all tests (backend + frontend)

test-backend: ## Run backend tests with coverage (must be ≥90%)
	@echo "Running backend tests..."
	@cd backend && \
	  source .venv/bin/activate && \
	  pytest tests/ \
	    --cov=app \
	    --cov-report=html:htmlcov \
	    --cov-report=term-missing \
	    --cov-fail-under=90 \
	    -v
	@echo "Coverage report: backend/htmlcov/index.html"

test-frontend: ## Run frontend tests with coverage
	@echo "Running frontend tests..."
	@cd frontend && npm run test:coverage

test-backend-watch: ## Run backend tests in watch mode
	@cd backend && \
	  source .venv/bin/activate && \
	  pytest tests/ --tb=short -v --watch

test-frontend-watch: ## Run frontend tests in watch mode
	@cd frontend && npm run test:watch

# ─── Code Quality ─────────────────────────────────────────────────────────────

lint: lint-backend lint-frontend ## Run all linters

lint-backend: ## Lint backend (ruff + mypy)
	@cd backend && source .venv/bin/activate && ruff check app/ tests/
	@cd backend && source .venv/bin/activate && mypy app/ --ignore-missing-imports
	@echo "Backend lint: OK"

lint-frontend: ## Lint frontend (ESLint + TypeScript)
	@cd frontend && npm run lint
	@cd frontend && npx tsc --noEmit
	@echo "Frontend lint: OK"

format: format-backend format-frontend ## Format all code

format-backend: ## Format backend code (black + isort)
	@cd backend && source .venv/bin/activate && black app/ tests/
	@cd backend && source .venv/bin/activate && isort app/ tests/
	@echo "Backend formatted"

format-frontend: ## Format frontend code (prettier)
	@cd frontend && npm run format
	@echo "Frontend formatted"

# ─── Database ─────────────────────────────────────────────────────────────────

migrate: ## Run pending Alembic migrations
	@cd backend && \
	  source .venv/bin/activate && \
	  alembic upgrade head
	@echo "Migrations applied"

migrate-new: ## Create a new migration (usage: make migrate-new MSG="add_users_table")
	@cd backend && \
	  source .venv/bin/activate && \
	  alembic revision \
	    --autogenerate \
	    -m "$(MSG)"
	@echo "Migration created in backend/alembic/versions/"

migrate-history: ## Show migration history
	@cd backend && \
	  source .venv/bin/activate && \
	  alembic history --verbose

migrate-rollback: ## Roll back one migration
	@cd backend && \
	  source .venv/bin/activate && \
	  alembic downgrade -1

# ─── Docker ───────────────────────────────────────────────────────────────────

build: ## Build Docker images locally
	@docker compose build

build-backend: ## Build backend Docker image only
	@docker build -t agentforge-backend:local ./backend/

build-frontend: ## Build frontend Docker image only
	@docker build \
	  --build-arg VITE_API_URL=http://localhost:8000 \
	  --build-arg VITE_WS_URL=ws://localhost:8000 \
	  -t agentforge-frontend:local \
	  ./frontend/

# ─── AWS Infrastructure ───────────────────────────────────────────────────────

infra-init: ## Initialise Terraform (run once per environment)
	@cd infrastructure/terraform && \
	  terraform init \
	    -backend-config="bucket=${PROJECT}-terraform-state" \
	    -backend-config="key=${PROJECT}/${ENVIRONMENT}/terraform.tfstate" \
	    -backend-config="region=${AWS_REGION}"

infra-plan: ## Preview infrastructure changes
	@cd infrastructure/terraform && \
	  terraform plan \
	    -var="environment=${ENVIRONMENT}" \
	    -var="aws_region=${AWS_REGION}"

infra-apply: ## Deploy / update AWS infrastructure
	@chmod +x scripts/deploy-infra.sh
	@bash scripts/deploy-infra.sh $(ENVIRONMENT)

infra-output: ## Show Terraform outputs
	@cd infrastructure/terraform && terraform output

infra-destroy: ## Destroy infrastructure (use with extreme caution!)
	@echo "WARNING: This will destroy ALL infrastructure for environment: $(ENVIRONMENT)"
	@echo "Type the environment name to confirm:"
	@read CONFIRM && [ "$$CONFIRM" = "$(ENVIRONMENT)" ] || (echo "Aborted" && exit 1)
	@cd infrastructure/terraform && \
	  terraform destroy \
	    -var="environment=${ENVIRONMENT}" \
	    -var="aws_region=${AWS_REGION}"

# ─── Deployment ───────────────────────────────────────────────────────────────

push: ## Build and push Docker images to ECR
	@chmod +x scripts/build-and-push.sh
	@bash scripts/build-and-push.sh $(ENVIRONMENT)

deploy-backend: ## Force new ECS backend deployment
	@aws ecs update-service \
	  --cluster  ${PROJECT}-${ENVIRONMENT}-cluster \
	  --service  ${PROJECT}-${ENVIRONMENT}-backend \
	  --force-new-deployment \
	  --region   $(AWS_REGION)
	@echo "Backend deployment triggered"

deploy-frontend: ## Force new ECS frontend deployment
	@aws ecs update-service \
	  --cluster ${PROJECT}-${ENVIRONMENT}-cluster \
	  --service ${PROJECT}-${ENVIRONMENT}-frontend \
	  --force-new-deployment \
	  --region  $(AWS_REGION)
	@echo "Frontend deployment triggered"

# ─── Utilities ────────────────────────────────────────────────────────────────

clean: ## Remove all build artifacts and caches
	@find . -type d -name __pycache__    -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache  -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .mypy_cache    -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.pyc"                -delete 2>/dev/null || true
	@rm -rf backend/htmlcov backend/.coverage backend/coverage.xml
	@rm -rf frontend/dist frontend/coverage
	@echo "Build artifacts cleaned"

health-check: ## Check local API health
	@curl -sf http://localhost:8000/api/v1/health | python3 -m json.tool || \
	  echo "API is not running. Start with: make dev-up"

version: ## Show tool versions
	@echo "Python:    $$(python3 --version)"
	@echo "Node:      $$(node --version)"
	@echo "npm:       $$(npm --version)"
	@echo "Docker:    $$(docker --version)"
	@echo "Terraform: $$(terraform --version | head -1)" 2>/dev/null || echo "Terraform: not installed"
	@echo "AWS CLI:   $$(aws --version)" 2>/dev/null || echo "AWS CLI:   not installed"
