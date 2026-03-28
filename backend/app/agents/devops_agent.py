import json
from typing import Any

from app.agents.base import BaseAgent

_SYSTEM_PROMPT = """You are a Senior DevOps/Platform Engineer who creates \
production-grade infrastructure and deployment configurations. You specialise in:
- Docker multi-stage builds for minimal, secure images
- CI/CD pipelines (GitHub Actions)
- docker-compose for local development
- Environment configuration management
- Health checks and graceful shutdown
- Security hardening (non-root users, read-only filesystems, secret management)"""


class DevOpsAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            name="DevOps",
            description="Creates Dockerfile, docker-compose, CI/CD, and configuration files",
        )

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        self._log_step("Setting up DevOps configurations...")

        specification = state.get("specification") or {}
        architecture  = state.get("architecture") or {}

        # Incorporate revision feedback if present
        all_feedback: list[dict] = state.get("human_feedback", [])
        final_feedback = [
            fb for fb in all_feedback
            if fb.get("step") == "final_review"
            and fb.get("action") == "modify"
        ]
        feedback_context = ""
        if final_feedback:
            latest = final_feedback[-1]
            feedback_context = (
                f"\n\nHuman Feedback (incorporate):\n{latest.get('feedback', '')}"
            )

        devops_files: list[dict] = []
        devops_files.append(await self._generate_dockerfile(specification, feedback_context))
        devops_files.append(await self._generate_docker_compose(specification, architecture))
        devops_files.append(await self._generate_cicd(specification))
        devops_files.append(await self._generate_env_example(specification))
        devops_files.append(await self._generate_makefile(specification))

        self._log_step(f"DevOps setup complete — {len(devops_files)} files")

        return {
            **state,
            "devops_files": devops_files,
            "current_step": "devops_setup",
        }

    async def _generate_dockerfile(
        self, specification: dict, feedback_context: str
    ) -> dict:
        content = await self._invoke_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_message=(
                f"Generate a production-grade multi-stage Dockerfile.\n"
                f"Language: {specification.get('target_language', 'Python')}\n"
                f"Framework: {specification.get('target_framework', '')}\n"
                f"Tech stack: {json.dumps(specification.get('tech_stack', {}))}\n"
                f"{feedback_context}\n\n"
                "Requirements:\n"
                "- Multi-stage build for minimal final image\n"
                "- Non-root user for security\n"
                "- HEALTHCHECK instruction\n"
                "- Proper layer caching (dependencies before code)\n"
                "- Build ARGs for configurable values\n"
                "- Graceful shutdown support (SIGTERM)\n\n"
                "Output ONLY the Dockerfile content."
            ),
        )
        return {"path": "Dockerfile", "content": content, "type": "dockerfile", "language": "dockerfile"}

    async def _generate_docker_compose(
        self, specification: dict, architecture: dict
    ) -> dict:
        db_type = architecture.get("database_schema", {}).get("type", "postgresql")
        content = await self._invoke_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_message=(
                f"Generate a docker-compose.yml for local development.\n"
                f"Project: {specification.get('project_name')}\n"
                f"Language: {specification.get('target_language')}\n"
                f"Framework: {specification.get('target_framework')}\n"
                f"Database: {db_type}\n"
                f"Tech stack: {json.dumps(specification.get('tech_stack', {}))}\n\n"
                "Include:\n"
                "- Application service with hot-reload volume mount\n"
                f"- {db_type} service with health check\n"
                "- Redis service (if needed) with health check\n"
                "- Proper named networks and volumes\n"
                "- Environment variables from .env file\n"
                "- Correct service dependency ordering\n\n"
                "Output ONLY the docker-compose.yml content."
            ),
        )
        return {"path": "docker-compose.yml", "content": content, "type": "docker-compose", "language": "yaml"}

    async def _generate_cicd(self, specification: dict) -> dict:
        content = await self._invoke_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_message=(
                f"Generate a GitHub Actions CI/CD workflow.\n"
                f"Project: {specification.get('project_name')}\n"
                f"Language: {specification.get('target_language')}\n"
                f"Framework: {specification.get('target_framework')}\n"
                f"Test framework: {specification.get('tech_stack', {}).get('testing', 'pytest')}\n\n"
                "Include jobs:\n"
                "1. test: lint + type check + unit tests with coverage (fail if <90%)\n"
                "2. security: Trivy vulnerability scan\n"
                "3. build: Docker multi-platform build + push to ECR (on main branch)\n"
                "4. deploy: ECS service update with rollback on failure (on tags)\n\n"
                "Use OIDC for AWS authentication (no static credentials).\n"
                "Output ONLY the .github/workflows/ci.yml content."
            ),
        )
        return {
            "path":     ".github/workflows/ci.yml",
            "content":  content,
            "type":     "cicd",
            "language": "yaml",
        }

    async def _generate_env_example(self, specification: dict) -> dict:
        content = await self._invoke_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_message=(
                f"Generate a .env.example file.\n"
                f"Project: {specification.get('project_name')}\n"
                f"Tech stack: {json.dumps(specification.get('tech_stack', {}))}\n\n"
                "Include all environment variables with:\n"
                "- Descriptive comments for each variable\n"
                "- Safe example values (not real secrets)\n"
                "- Grouped by service/component\n"
                "- Indication of which are required vs optional\n\n"
                "Output ONLY the .env.example content."
            ),
        )
        return {"path": ".env.example", "content": content, "type": "config", "language": "bash"}

    async def _generate_makefile(self, specification: dict) -> dict:
        content = await self._invoke_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_message=(
                f"Generate a Makefile.\n"
                f"Project: {specification.get('project_name')}\n"
                f"Language: {specification.get('target_language')}\n"
                f"Test framework: {specification.get('tech_stack', {}).get('testing', 'pytest')}\n\n"
                "Include targets: help, setup, dev, test, test-cov, lint, format, "
                "build, up, down, migrate, clean.\n"
                "Add a self-documenting help target using ## comments.\n\n"
                "Output ONLY the Makefile content."
            ),
        )
        return {"path": "Makefile", "content": content, "type": "makefile", "language": "makefile"}
