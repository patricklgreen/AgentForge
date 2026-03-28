import json
from typing import Any

from app.agents.base import BaseAgent

_SYSTEM_PROMPT = """You are a Technical Writer who creates clear, comprehensive \
documentation for software projects. You write documentation that:
- Enables a new developer to be productive within 30 minutes
- Explains the 'why' behind architectural decisions, not just the 'what'
- Includes working code examples and curl commands
- Follows best practices from successful open-source projects (React, FastAPI, etc.)"""


class DocumentationAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            name="Documentation",
            description="Generates README, API docs, architecture decisions, and contributing guide",
        )

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        self._log_step("Generating documentation...")

        specification = state.get("specification") or {}
        architecture  = state.get("architecture") or {}
        review        = state.get("review_comments") or {}

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

        docs: list[dict] = []
        docs.append(await self._generate_readme(specification, architecture, feedback_context))

        if specification.get("api_endpoints"):
            docs.append(await self._generate_api_docs(specification))

        docs.append(await self._generate_adr(specification, architecture))
        docs.append(await self._generate_contributing(specification))

        # Generate .agentforge.yaml project memory file
        docs.append(self._generate_agentforge_yaml(specification, architecture, review))

        self._log_step(f"Documentation complete — {len(docs)} documents")

        return {
            **state,
            "documentation": {"files": docs, "summary": specification.get("project_summary", "")},
            "current_step":  "documentation",
        }

    async def _generate_readme(
        self,
        specification:    dict,
        architecture:     dict,
        feedback_context: str,
    ) -> dict:
        content = await self._invoke_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_message=(
                f"Generate a comprehensive README.md.\n\n"
                f"Project: {specification.get('project_name')}\n"
                f"Summary: {specification.get('project_summary')}\n"
                f"Language: {specification.get('target_language')}\n"
                f"Framework: {specification.get('target_framework')}\n"
                f"Architecture: {architecture.get('architecture_pattern')}\n"
                f"Tech stack: {json.dumps(specification.get('tech_stack', {}))}\n"
                f"Key features: "
                f"{[fr['title'] for fr in specification.get('functional_requirements', [])[:10]]}\n"
                f"{feedback_context}\n\n"
                "Include:\n"
                "- Project title with CI, coverage, and license badges\n"
                "- Description and key features list\n"
                "- Architecture diagram (Mermaid or ASCII)\n"
                "- Prerequisites with version requirements\n"
                "- Quick Start (clone → configure → run in under 5 steps)\n"
                "- Environment variables table\n"
                "- API overview with example curl requests\n"
                "- Running tests and checking coverage\n"
                "- Deployment instructions\n"
                "- Contributing section\n"
                "- License\n\n"
                "Output ONLY the README.md content."
            ),
        )
        return {"path": "README.md", "content": content, "type": "documentation", "language": "markdown"}

    async def _generate_api_docs(self, specification: dict) -> dict:
        content = await self._invoke_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_message=(
                f"Generate comprehensive API documentation in Markdown.\n\n"
                f"Project: {specification.get('project_name')}\n"
                f"Auth: {specification.get('tech_stack', {}).get('auth', 'JWT')}\n\n"
                f"Endpoints:\n"
                f"{json.dumps(specification.get('api_endpoints', []), indent=2)[:5000]}\n\n"
                f"Data Models:\n"
                f"{json.dumps(specification.get('data_models', []), indent=2)[:3000]}\n\n"
                "For each endpoint document:\n"
                "- HTTP method and path\n"
                "- Description and use case\n"
                "- Authentication requirements\n"
                "- Request headers, body schema, and example\n"
                "- Response schema and example\n"
                "- All error response codes\n\n"
                "Output ONLY the docs/API.md content."
            ),
        )
        return {"path": "docs/API.md", "content": content, "type": "documentation", "language": "markdown"}

    async def _generate_adr(
        self, specification: dict, architecture: dict
    ) -> dict:
        content = await self._invoke_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_message=(
                f"Generate Architecture Decision Records (ADRs).\n\n"
                f"Architecture pattern: {architecture.get('architecture_pattern')}\n"
                f"Key patterns: {architecture.get('key_patterns', [])}\n"
                f"Design decisions:\n"
                f"{json.dumps(architecture.get('design_decisions', []), indent=2)[:4000]}\n\n"
                "Format each ADR:\n"
                "## ADR-NNN: Title\n"
                "**Status:** Accepted\n"
                "**Context:** Why was this decision needed?\n"
                "**Decision:** What was decided?\n"
                "**Consequences:** What are the trade-offs?\n"
                "**Alternatives Considered:** What else was evaluated?\n\n"
                "Output ONLY the docs/ARCHITECTURE.md content."
            ),
        )
        return {"path": "docs/ARCHITECTURE.md", "content": content, "type": "documentation", "language": "markdown"}

    async def _generate_contributing(self, specification: dict) -> dict:
        content = await self._invoke_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_message=(
                f"Generate a CONTRIBUTING.md.\n\n"
                f"Project: {specification.get('project_name')}\n"
                f"Language: {specification.get('target_language')}\n\n"
                "Include:\n"
                "- Code of conduct reference\n"
                "- Bug reporting and feature request process\n"
                "- Development setup\n"
                "- Coding standards and style guide\n"
                "- Testing requirements (90%+ coverage mandatory)\n"
                "- Pull request process and review criteria\n"
                "- Conventional Commits format\n"
                "- Branch naming conventions (feat/, fix/, chore/)\n\n"
                "Output ONLY the CONTRIBUTING.md content."
            ),
        )
        return {
            "path":     "CONTRIBUTING.md",
            "content":  content,
            "type":     "documentation",
            "language": "markdown",
        }

    @staticmethod
    def _generate_agentforge_yaml(
        specification: dict,
        architecture:  dict,
        review:        dict,
    ) -> dict:
        """Generate a .agentforge.yaml project memory file."""
        from datetime import datetime, timezone

        content_lines = [
            "# AgentForge project memory — do not edit manually",
            f"agentforge_version: '1.0.0'",
            f"generated_at: '{datetime.now(timezone.utc).isoformat()}'",
            "",
            "project:",
            f"  name: {specification.get('project_name', 'application')}",
            f"  language: {specification.get('target_language', '')}",
            f"  framework: {specification.get('target_framework', '')}",
            f"  architecture: {architecture.get('architecture_pattern', '')}",
            "",
            "quality:",
            f"  review_score: {review.get('overall_score', 0)}",
            f"  estimated_coverage: "
            f"{review.get('test_coverage_assessment', {}).get('estimated_coverage', 0)}",
            f"  critical_issues: {len(review.get('critical_issues', []))}",
            "",
            "tech_stack:",
        ]

        for k, v in specification.get("tech_stack", {}).items():
            if v:
                content_lines.append(f"  {k}: {v}")

        return {
            "path":     ".agentforge.yaml",
            "content":  "\n".join(content_lines) + "\n",
            "type":     "config",
            "language": "yaml",
        }
