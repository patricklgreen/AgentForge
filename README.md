# AgentForge 🤖

> AI-powered application builder — describe what you need, agents build it.

[![CI/CD](https://github.com/your-org/agentforge/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/agentforge/actions)
[![Coverage](https://codecov.io/gh/your-org/agentforge/branch/main/graph/badge.svg)](https://codecov.io/gh/your-org/agentforge)

## Architecture

```
Requirements → Analysis → Architecture → Code Gen → Tests → Review → DevOps → Docs → ZIP
                   ↑ Human Review       ↑ Human Review   ↑ Human Review        ↑ Final Review
```

**Stack:**
- **Backend**: FastAPI + LangGraph + AWS Bedrock (Claude 3.5 Sonnet)
- **Frontend**: React + TypeScript + Vite + Tailwind CSS  
- **Database**: PostgreSQL (RDS) + Redis (ElastiCache)
- **Infrastructure**: AWS ECS Fargate via Terraform
- **AI**: Anthropic Claude via AWS Bedrock

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

Your AWS credentials need:
```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:InvokeModel",
    "bedrock:InvokeModelWithResponseStream",
    "s3:GetObject",
    "s3:PutObject",
    "s3:ListBucket"
  ]
}
```

### Enable Bedrock Model Access

In AWS Console → Bedrock → Model Access → Request access for:
- `Claude 3.5 Sonnet v2`
- `Claude 3.5 Haiku`

## Running Tests

```bash
make test           # Run all tests
make test-backend   # Backend only (requires 90% coverage)
make test-frontend  # Frontend only
```

## Deploy to AWS

```bash
# 1. Create Terraform state bucket first
aws s3 mb s3://agentforge-terraform-state --region us-east-1

# 2. Configure variables
cp infrastructure/terraform/terraform.tfvars.example \
   infrastructure/terraform/terraform.tfvars
# Edit terraform.tfvars with your values

# 3. Deploy infrastructure
export TF_VAR_db_password="your-strong-password"
export TF_VAR_secret_key="your-32-char-secret-key"
make infra-apply

# 4. Build and push Docker images
make push ENVIRONMENT=prod

# 5. Deploy application
# CI/CD handles this automatically on main branch push
```

## How It Works

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

## Project Structure

```
agentforge/
├── backend/
│   ├── app/
│   │   ├── agents/          # AI agent implementations
│   │   ├── api/routes/      # FastAPI endpoints
│   │   ├── models/          # SQLAlchemy models
│   │   ├── schemas/         # Pydantic schemas
│   │   └── services/        # Bedrock, S3, WebSocket
│   └── tests/
│       ├── unit/            # Unit tests
│       └── integration/     # Integration tests
├── frontend/
│   └── src/
│       ├── components/      # React components
│       ├── pages/           # Page components
│       ├── api/             # API client
│       └── store/           # Zustand state
├── infrastructure/
│   └── terraform/           # AWS infrastructure
└── scripts/                 # Setup and deployment scripts
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
