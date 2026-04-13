import json
from typing import Any

from app.agents.base import BaseAgent
from app.agents.directive_config_generator import directive_config_generator

_SYSTEM_PROMPT = """You are a Senior DevOps/Platform Engineer following the deftai/directive framework.

You create production-grade infrastructure and deployment configurations that follow:
! Directive-based best practices and patterns
! Security-first approach (non-root users, minimal images, secrets management)  
! Docker multi-stage builds for minimal, secure images
! Modern CI/CD pipelines (GitHub Actions, automated testing)
! Task-based automation (Taskfile.yml over Makefiles)
! Infrastructure as Code principles
! Observability and monitoring integration
! Cross-platform compatibility (Linux, macOS, Windows)

~ Follow container security best practices
~ Use Alpine Linux for smaller images where appropriate  
~ Include comprehensive health checks and monitoring
~ Implement proper logging and error handling
≉ Use 'latest' tags in production configurations
⊗ Include secrets or credentials in configuration files

Generate production-ready configurations that follow directive standards."""


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
        
        # Generate directive-based configuration files first
        project_directive = await directive_config_generator.generate_project_directive(specification)
        agents_md = await directive_config_generator.generate_agents_md(specification)
        taskfile_yml = await directive_config_generator.generate_taskfile_yml(specification)
        
        # Add directive configuration files
        devops_files.append({
            "path": "PROJECT.md",
            "content": project_directive,
            "type": "directive_config",
            "language": "markdown"
        })
        devops_files.append({
            "path": "AGENTS.md", 
            "content": agents_md,
            "type": "directive_config",
            "language": "markdown"
        })
        devops_files.append({
            "path": "Taskfile.yml",
            "content": taskfile_yml,
            "type": "taskfile",
            "language": "yaml"
        })
        
        # Generate traditional DevOps files
        devops_files.append(await self._generate_dockerfile(specification, feedback_context))
        devops_files.append(await self._generate_docker_compose(specification, architecture))
        devops_files.append(await self._generate_cicd(specification))
        devops_files.append(await self._generate_env_example(specification))

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
            include_directive=True,
            state={
                "specification": specification,
                "requirements": specification.get("project_description", "")
            }
        )
        return {"path": ".env.example", "content": content, "type": "config", "language": "bash"}

    async def _generate_makefile(self, specification: dict) -> dict:
        """Generate a Taskfile.yml (directive-preferred) instead of Makefile"""
        content = await self._invoke_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_message=(
                f"Generate a Taskfile.yml for task automation.\n"
                f"Project: {specification.get('project_name')}\n"
                f"Language: {specification.get('target_language')}\n"
                f"Framework: {specification.get('target_framework', '')}\n"
                f"Test framework: {specification.get('tech_stack', {}).get('testing', 'pytest')}\n\n"
                "Follow the directive framework task automation standards:\n"
                "Include these standard tasks with proper desc: fields:\n"
                "- dev: Start development environment\n"
                "- test: Run tests in watch mode\n"
                "- test:coverage: Run tests with coverage report\n"
                "- check: Pre-commit checks (lint, format, type-check, test)\n"
                "- build: Build the application\n"
                "- clean: Clean build artifacts\n"
                "- setup: Install dependencies and setup project\n"
                "- format: Format code\n"
                "- lint: Run linter\n\n"
                "Use proper task dependencies, preconditions, and sources/generates where appropriate.\n"
                "Ensure cross-platform compatibility.\n\n"
                "Output ONLY the Taskfile.yml content."
            ),
            include_directive=True,
            state={
                "specification": specification,
                "requirements": specification.get("project_description", "")
            }
        )
        return {"path": "Taskfile.yml", "content": content, "type": "taskfile", "language": "yaml"}
