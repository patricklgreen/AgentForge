# AgentForge 🤖

> AI-powered application builder — describe what you need, agents build it.

[![CI/CD](https://github.com/your-org/agentforge/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/agentforge/actions)
[![Coverage](https://codecov.io/gh/your-org/agentforge/branch/main/graph/badge.svg)](https://codecov.io/gh/your-org/agentforge)
[![Backend Tests](https://img.shields.io/badge/backend%20coverage-90%2B%25-green)](./backend/htmlcov/index.html)
[![Frontend Tests](https://img.shields.io/badge/frontend%20tests-14%20suites-blue)](./frontend/src/__tests__)

## 🏗️ Architecture

AgentForge uses a multi-agent AI system with human-in-the-loop reviews at critical stages:

```
Requirements → Analysis → Architecture → Code Gen → Tests → Review → DevOps → Docs → ZIP
     ↓             ↑ Human Review       ↑ Human Review   ↑ Human Review        ↑ Final Review
User Input    Requirements     Architecture     Code & Tests     DevOps & Docs    Download
              Specification    Design           (90%+ Coverage)   Configuration    Archive
```

**Technology Stack:**
- **Backend**: FastAPI + LangGraph + AWS Bedrock (Claude 3.5 Sonnet)
- **Frontend**: React 18 + TypeScript + Vite + Tailwind CSS  
- **Database**: PostgreSQL (RDS) + Redis (ElastiCache)
- **Infrastructure**: AWS ECS Fargate via Terraform
- **AI Models**: Claude 3.5 Sonnet v2 (primary) + Claude 3.5 Haiku (fast operations)
- **Auth**: JWT + API Keys with role-based access control
- **Testing**: pytest + Vitest with 90%+ coverage requirement

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Node.js 20+
- AWS CLI configured with Bedrock access

### Local Development

```bash
# Clone and setup
git clone https://github.com/3Ci-Consulting/agentforge
cd agentforge
cp .env.example .env  # Fill in your AWS credentials

# One-command setup
make setup

# Start everything
make dev-up

# Open http://localhost:3000
```

### Required AWS Permissions

Your AWS credentials need access to Bedrock and S3:
```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:InvokeModel",
    "bedrock:InvokeModelWithResponseStream",
    "bedrock:ListFoundationModels",
    "s3:GetObject",
    "s3:PutObject",
    "s3:ListBucket",
    "s3:DeleteObject"
  ],
  "Resource": [
    "arn:aws:bedrock:*:*:foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0",
    "arn:aws:bedrock:*:*:foundation-model/anthropic.claude-3-5-haiku-20241022-v1:0",
    "arn:aws:s3:::your-bucket-name/*",
    "arn:aws:s3:::your-bucket-name"
  ]
}
```

### Enable Bedrock Model Access

In AWS Console → Bedrock → Model Access → Request access for:
- `Claude 3.5 Sonnet v2`
- `Claude 3.5 Haiku`

## 🧪 Testing & Quality Assurance

AgentForge maintains high code quality standards with comprehensive test coverage:

### Test Coverage Metrics

| Component | Coverage | Test Suites | Test Count |
|-----------|----------|-------------|------------|
| **Backend** | 90%+ enforced | 6 suites | 105 tests |
| **Frontend** | 14 test suites | Components, Pages, Store, API | 50+ tests |
| **Integration** | Auth + Projects | API endpoints, security | 40+ tests |

### Running Tests

```bash
# Run all tests with coverage
make test

# Backend tests (enforces 90% coverage)
make test-backend

# Frontend tests with coverage
make test-frontend

# View coverage reports
open backend/htmlcov/index.html        # Backend detailed coverage
open frontend/coverage/index.html      # Frontend coverage report
```

### Test Structure

**Backend (`backend/tests/`)**
- **Unit tests**: Service layer, business logic, utilities
- **Integration tests**: API endpoints, database operations, authentication
- **Fixtures**: Reusable test data and mock objects
- **Coverage**: Line coverage ≥90%, branch coverage ≥85%

**Frontend (`frontend/src/__tests__/`)**
- **Component tests**: UI components, user interactions
- **Page tests**: Full page rendering, routing, forms
- **Store tests**: State management, API integration
- **API tests**: Client functions, error handling

## 🚀 Deploy to AWS

### Production Deployment

```bash
# 1. Create Terraform state bucket first
aws s3 mb s3://agentforge-terraform-state-$(date +%s) --region us-east-1

# 2. Configure infrastructure variables
cp infrastructure/terraform/terraform.tfvars.example \
   infrastructure/terraform/terraform.tfvars
# Edit terraform.tfvars with your values:
#   - domain_name = "yourdomain.com" 
#   - db_password = "your-strong-password"
#   - allowed_origins = ["https://yourdomain.com"]

# 3. Deploy infrastructure
export TF_VAR_db_password="your-strong-password"
export TF_VAR_secret_key="$(openssl rand -hex 32)"
make infra-apply

# 4. Build and push Docker images
make push ENVIRONMENT=prod

# 5. Deploy application (automated via CI/CD)
# Deployments happen automatically on:
#   - Push to main branch → latest deployment
#   - Tagged release → versioned deployment
```

### CI/CD Pipeline Features
- **Automated testing** with 90% coverage enforcement
- **Security scanning** with Trivy vulnerability scanner
- **Multi-stage deployment** with database migrations
- **Blue-green deployment** with automatic rollback on failure
- **Health checks** and smoke tests post-deployment
- **OIDC authentication** for secure AWS access (no long-lived credentials)

### Monitoring & Observability
- **Structured logging** with correlation IDs
- **Health check endpoints** for load balancer monitoring  
- **ECS service monitoring** with CloudWatch metrics
- **Database connection pooling** and query optimization
- **Redis caching** for session management and rate limiting

## ✨ Features

### 🔐 Authentication & Security
- **JWT-based authentication** with access/refresh tokens
- **API key support** for programmatic access
- **Role-based access control** (User, Admin roles)
- **User registration and profile management**
- **Session management** with automatic token refresh
- **Security event logging** for audit trails

### 🤖 AI Agent System
- **Multi-agent orchestration** with LangGraph workflow engine
- **Specialized AI agents**:
  - Requirements Analyst: Converts user input to technical specifications
  - System Architect: Designs system architecture and component interactions
  - Code Generator: Creates source code from specifications
  - Test Writer: Generates comprehensive test suites (90%+ coverage)
  - Code Reviewer: Performs automated code quality and security analysis
  - DevOps Agent: Creates Docker, CI/CD, and deployment configurations
  - Documentation Agent: Generates README, API docs, architecture decisions
- **Human-in-the-loop reviews** at critical decision points
- **Real-time WebSocket updates** for agent progress

### 📊 Project Management
- **Project lifecycle tracking** through all development phases
- **Artifact management** with S3 storage for generated code
- **Run history** with detailed event logs and timestamps
- **Download packaging** of complete project archives
- **Multi-user support** with project ownership controls

### 🎨 Modern Frontend
- **React 18** with TypeScript and modern hooks
- **Responsive design** with Tailwind CSS
- **Real-time updates** via WebSocket connections
- **Protected routes** with authentication guards
- **Rich UI components** for project creation and monitoring
- **Monaco Editor** integration for code review
- **State management** with Zustand store

## 🚀 How It Works

### Development Workflow
1. **Create a Project** — Provide your business requirements in detail
2. **Requirements Review** — AI analyst produces a technical specification → you approve
3. **Architecture Review** — AI architect designs the system → you approve  
4. **Code Generation** — Code generator creates all source files
5. **Automated Testing** — Test writer creates 90%+ coverage test suite
6. **Code Review** — Automated review scores quality, flags security issues
7. **Human Code Review** — You review code and tests → approve or request changes
8. **DevOps** — Docker, CI/CD, and configuration files generated
9. **Documentation** — README, API docs, architecture decisions written
10. **Final Review** — Approve for packaging → download complete ZIP archive

### Agent Orchestration
Each agent is a specialized AI system with domain expertise:
- **Requirements Analyst**: Business analysis, feature decomposition, technical writing
- **System Architect**: System design, database modeling, API design patterns
- **Code Generator**: Multi-language code generation, framework integration
- **Test Writer**: Unit testing, integration testing, coverage optimization
- **Code Reviewer**: Static analysis, security scanning, best practices
- **DevOps Agent**: Containerization, CI/CD pipelines, deployment automation
- **Documentation Agent**: Technical writing, API documentation, architecture docs

### Quality Gates
- **90%+ test coverage** enforced at build time
- **Type checking** with TypeScript/mypy
- **Code linting** with ESLint/Ruff
- **Security scanning** with Trivy
- **Human approval** required at architecture and final review stages

## 📁 Project Structure

```
agentforge/
├── backend/                         # FastAPI backend application
│   ├── app/
│   │   ├── agents/                  # AI agent implementations (15 files)
│   │   │   ├── orchestrator.py      # Main workflow coordination
│   │   │   ├── requirements_analyst.py
│   │   │   ├── architect.py         # System architecture design
│   │   │   ├── code_generator.py    # Multi-language code generation
│   │   │   ├── test_writer.py       # Test suite generation
│   │   │   ├── code_reviewer.py     # Quality & security analysis
│   │   │   ├── devops_agent.py      # CI/CD & deployment config
│   │   │   ├── documentation_agent.py
│   │   │   ├── validation_agent.py  # Output validation
│   │   │   └── language_profiles.py # Language-specific templates
│   │   ├── api/routes/              # FastAPI endpoints
│   │   │   ├── auth.py              # Authentication & user management
│   │   │   ├── projects.py          # Project lifecycle management
│   │   │   └── artifacts.py         # File storage & retrieval
│   │   ├── auth/                    # Authentication system
│   │   │   ├── models.py            # User, role models
│   │   │   ├── schemas.py           # Pydantic validation schemas
│   │   │   └── service.py           # Auth business logic
│   │   ├── models/                  # SQLAlchemy database models
│   │   ├── schemas/                 # API request/response schemas
│   │   ├── services/                # External service integrations
│   │   │   ├── bedrock.py           # AWS Bedrock AI service
│   │   │   ├── s3.py                # File storage
│   │   │   └── websocket_manager.py # Real-time updates
│   │   └── utils/                   # Shared utilities
│   ├── tests/                       # Test suites (105 tests)
│   │   ├── unit/                    # Service layer tests
│   │   │   ├── test_auth_service.py
│   │   │   └── test_agents.py
│   │   ├── integration/             # API endpoint tests
│   │   │   ├── test_auth_api.py     # Authentication flow tests
│   │   │   └── test_api_projects.py # Project management tests
│   │   ├── conftest.py              # Shared test configuration
│   │   └── auth_fixtures.py         # Authentication test fixtures
│   ├── alembic/                     # Database migrations
│   ├── Dockerfile                   # Container configuration
│   └── requirements.txt             # Python dependencies
├── frontend/                        # React TypeScript frontend
│   ├── src/
│   │   ├── components/              # Reusable UI components
│   │   │   ├── Layout.tsx           # Application shell
│   │   │   ├── ProtectedRoute.tsx   # Authentication guard
│   │   │   └── AgentTimeline.tsx    # Agent progress display
│   │   ├── pages/                   # Application pages
│   │   │   ├── Login.tsx            # Authentication
│   │   │   ├── Register.tsx         # User registration
│   │   │   ├── Dashboard.tsx        # Project overview
│   │   │   ├── NewProject.tsx       # Project creation
│   │   │   ├── ProjectDetail.tsx    # Project management
│   │   │   └── Profile.tsx          # User profile management
│   │   ├── store/                   # Zustand state management
│   │   │   └── index.ts             # Auth & project stores
│   │   ├── api/                     # Backend API client
│   │   │   └── client.ts            # HTTP client with auth
│   │   ├── __tests__/               # Frontend test suites (14 suites)
│   │   │   ├── components/          # Component unit tests
│   │   │   ├── pages/               # Page integration tests
│   │   │   ├── store/               # State management tests
│   │   │   └── api/                 # API client tests
│   │   └── types/                   # TypeScript type definitions
│   ├── Dockerfile                   # Frontend container
│   └── package.json                 # Node.js dependencies
├── infrastructure/
│   └── terraform/                   # AWS infrastructure as code
│       ├── main.tf                  # ECS, RDS, ElastiCache, ALB
│       ├── variables.tf             # Configuration variables
│       └── outputs.tf               # Infrastructure outputs
├── .github/
│   └── workflows/
│       └── ci.yml                   # CI/CD pipeline (396 lines)
├── scripts/                         # Setup and deployment scripts
└── docker-compose.yml               # Local development environment
```

**Key Metrics:**
- **Backend**: 5,719 Python files, 15 AI agents, 105+ tests
- **Frontend**: 173 TypeScript files, 14 test suites, 7 pages
- **Infrastructure**: Terraform for AWS ECS deployment
- **CI/CD**: Full pipeline with testing, security scanning, deployment

## 📚 Development

### Code Quality Standards
- **Type Safety**: TypeScript frontend, Python type hints with mypy
- **Code Formatting**: Prettier (frontend), Black (backend)  
- **Linting**: ESLint (frontend), Ruff (backend)
- **Testing**: Jest/Vitest (frontend), pytest (backend)
- **Coverage**: 90%+ enforced in CI/CD pipeline
- **Security**: Trivy scanning, dependency updates, secure defaults

### Contributing

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Write tests** for your changes (maintain 90%+ coverage)
4. **Run quality checks**: `make lint test`
5. **Commit** your changes (`git commit -m 'Add amazing feature'`)
6. **Push** to your branch (`git push origin feature/amazing-feature`)
7. **Create** a Pull Request

### Development Commands

```bash
# Setup and start development environment
make setup && make dev-up

# Code quality and testing
make lint          # Run all linters
make format        # Format all code
make test          # Run all tests with coverage
make clean         # Clean build artifacts

# Database operations  
make migrate       # Run latest migrations
make migrate-new   # Create new migration

# Production builds
make build         # Build Docker images locally
make push          # Build and push to ECR
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed contribution guidelines.

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

**AgentForge** - AI-powered application development that bridges the gap between business requirements and production-ready code. Built with enterprise-grade security, scalability, and comprehensive testing standards.
