import asyncio
import os
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.main import app
from app.database import Base, get_db

# ─── Test database ─────────────────────────────────────────────────────────────
# Use a real PostgreSQL test DB to avoid SQLite dialect mismatches with
# UUID columns, JSON columns, and PostgreSQL-specific enum types.
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://agentforge:password@localhost:5432/agentforge_test",
)


# ─── Event loop ────────────────────────────────────────────────────────────────
# pytest-asyncio >= 0.22 uses the "auto" asyncio_mode in pyproject.toml.
# A session-scoped event loop is no longer needed; each test gets its own.


# ─── Database fixtures ─────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create all tables once per test session."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a rolled-back session for each test (no data leaks)."""
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client with the DB session overridden."""

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ─── Service mocks ─────────────────────────────────────────────────────────────

@pytest.fixture
def mock_bedrock():
    """Mock the module-level bedrock_service singleton."""
    from unittest.mock import patch

    with patch("app.services.bedrock.bedrock_service") as mock:
        mock.invoke = AsyncMock(return_value="Mocked LLM response")
        mock.invoke_with_json_output = AsyncMock(
            return_value={"mocked": "response"}
        )
        mock.get_llm = MagicMock(
            return_value=MagicMock(
                ainvoke=AsyncMock(
                    return_value=MagicMock(content="# mocked code")
                )
            )
        )
        mock.get_fast_llm = MagicMock(
            return_value=MagicMock(
                ainvoke=AsyncMock(
                    return_value=MagicMock(content="# mocked fast response")
                )
            )
        )
        yield mock


@pytest.fixture
def mock_s3():
    """Mock the module-level s3_service singleton."""
    from unittest.mock import patch

    with patch("app.services.s3.s3_service") as mock:
        mock.upload_content            = AsyncMock(return_value="s3/test/key")
        mock.download_content          = AsyncMock(return_value="file content")
        mock.upload_project_artifact   = AsyncMock(return_value="s3/test/artifact")
        mock.create_project_zip        = AsyncMock(return_value="s3/test/project.zip")
        mock.get_presigned_url         = AsyncMock(
            return_value="https://s3.amazonaws.com/presigned"
        )
        mock.object_exists             = AsyncMock(return_value=True)
        yield mock


@pytest.fixture
def mock_ws_manager():
    """Mock the module-level ws_manager singleton."""
    from unittest.mock import patch

    with patch("app.services.websocket_manager.ws_manager") as mock:
        mock.send_agent_event  = AsyncMock()
        mock.send_interrupt    = AsyncMock()
        mock.broadcast_to_run  = AsyncMock()
        yield mock


@pytest.fixture
def mock_orchestrator():
    """Full orchestrator mock for route-level tests."""
    mock = MagicMock()
    mock.initialize  = AsyncMock()
    mock.start_run   = AsyncMock(
        return_value={
            "status":           "interrupted",
            "interrupt_payload": {
                "step":        "requirements_analysis",
                "title":       "Review Requirements",
                "description": "Please review",
                "data":        {},
            },
        }
    )
    mock.resume_run  = AsyncMock(
        return_value={"status": "completed", "interrupt_payload": None}
    )
    mock.get_run_state = AsyncMock(return_value={"zip_url": None})
    mock.cancel_run  = AsyncMock(return_value=True)
    return mock


# ─── Data fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def sample_project_data() -> dict:
    return {
        "name":             "Test E-Commerce API",
        "description":      "A RESTful API for an e-commerce platform",
        "requirements": (
            "Build a RESTful API for an e-commerce platform with: "
            "user registration and JWT authentication, product catalog with categories, "
            "shopping cart management, order processing with status tracking, "
            "inventory management, and an admin panel for product management. "
            "The system must support role-based access control with Admin and Customer roles."
        ),
        "target_language":  "Python",
        "target_framework": "FastAPI",
    }


@pytest.fixture
def sample_specification() -> dict:
    return {
        "project_name":    "ecommerce-api",
        "project_summary": "A production-ready e-commerce REST API built with FastAPI.",
        "target_language": "Python",
        "target_framework": "FastAPI",
        "functional_requirements": [
            {
                "id":    "FR-001",
                "title": "User Authentication",
                "description": "Users can register and authenticate via JWT tokens.",
                "priority": "must",
                "user_story": "As a user, I want to register and log in.",
                "acceptance_criteria": [
                    "User can register with email and password",
                    "User can log in and receive a JWT token",
                ],
                "affected_entities": ["User"],
            }
        ],
        "non_functional_requirements": [
            {
                "id":       "NFR-001",
                "category": "performance",
                "description": "API response time < 200ms",
                "metric": "p95 < 200ms",
                "implementation_hint": "Use database indexes and Redis caching.",
            }
        ],
        "user_roles": [
            {"name": "Admin",    "description": "Full access", "permissions": ["*"]},
            {"name": "Customer", "description": "Read/write own data", "permissions": ["read:products"]},
        ],
        "data_models": [
            {
                "name":        "User",
                "description": "Application user entity",
                "fields": [
                    {"name": "id",    "type": "uuid",   "required": True, "unique": True,
                     "indexed": True,  "description": "Primary key", "validation_rules": []},
                    {"name": "email", "type": "string", "required": True, "unique": True,
                     "indexed": True,  "description": "Email address",
                     "validation_rules": ["valid email format"]},
                ],
                "relationships": [
                    {"type": "one_to_many", "target": "Order", "description": "User has many orders"}
                ],
                "business_rules": ["Email must be unique across all users"],
            }
        ],
        "api_endpoints": [
            {
                "method":         "POST",
                "path":           "/api/v1/auth/register",
                "description":    "Register a new user account",
                "auth_required":  False,
                "required_roles": [],
                "path_params":    [],
                "query_params":   [],
                "request_body":   {"description": "User credentials", "schema": {}},
                "response":       {"status_code": 201, "description": "Created user", "schema": {}},
                "error_responses": [{"status_code": 409, "description": "Email already exists"}],
            }
        ],
        "integrations": [],
        "tech_stack": {
            "language":        "Python",
            "framework":       "FastAPI",
            "database":        "PostgreSQL",
            "cache":           "Redis",
            "auth":            "JWT",
            "testing":         "pytest",
            "orm":             "SQLAlchemy",
            "task_queue":      None,
            "search":          None,
            "file_storage":    "S3",
            "observability":   "structlog",
            "ci_cd":           "GitHub Actions",
            "containerisation": "Docker",
            "additional":      [],
        },
        "constraints":      ["Must run on AWS"],
        "assumptions":      ["Users have valid email addresses"],
        "open_questions":   [],
        "out_of_scope":     ["Mobile application"],
        "glossary":         [{"term": "JWT", "definition": "JSON Web Token"}],
    }


@pytest.fixture
def sample_architecture() -> dict:
    return {
        "architecture_pattern": "layered",
        "design_decisions": [
            {
                "decision":     "Use FastAPI with SQLAlchemy async",
                "rationale":    "Best async support for Python APIs",
                "alternatives": ["Django REST Framework", "Flask"],
            }
        ],
        "components": [
            {
                "name":         "API Layer",
                "layer":        "presentation",
                "responsibility": "Handle HTTP requests",
                "dependencies": ["Application Layer"],
                "files":        ["app/api/routes/users.py"],
            }
        ],
        "database_schema": {
            "type": "postgresql",
            "tables": [
                {
                    "name":    "users",
                    "columns": [
                        {"name": "id",    "type": "uuid", "constraints": ["PRIMARY KEY"]},
                        {"name": "email", "type": "varchar(255)", "constraints": ["UNIQUE", "NOT NULL"]},
                    ],
                    "indexes":      ["idx_users_email"],
                    "foreign_keys": [],
                }
            ],
        },
        "api_design": {
            "style":          "REST",
            "versioning":     "URL path (/api/v1)",
            "authentication": "JWT Bearer token",
            "base_url":       "/api/v1",
        },
        "key_patterns":             ["Repository Pattern", "Dependency Injection"],
        "security_considerations":  ["Use bcrypt for passwords", "Validate all inputs"],
        "scalability_notes":        ["Use Redis for caching", "Async throughout"],
        "files_to_generate": [
            {
                "path":         "app/main.py",
                "description":  "FastAPI application entry point",
                "component":    "API Layer",
                "priority":     1,
                "dependencies": [],
            },
            {
                "path":         "app/models/user.py",
                "description":  "User SQLAlchemy model",
                "component":    "Domain Layer",
                "priority":     2,
                "dependencies": ["app/database.py"],
            },
        ],
    }
