import json
from typing import Any

from app.agents.base import BaseAgent

_SYSTEM_PROMPT = """You are a Principal Software Architect with expertise in designing \
scalable, maintainable software systems. You follow SOLID principles, clean architecture, \
and industry best practices.

You produce detailed project structures with clear separation of concerns, proper layering, \
and comprehensive configuration. Your architectures are production-ready from day one.

Key responsibilities:
- Choose the right architecture pattern for the requirements
- Design clear component boundaries and dependencies
- Define the complete file structure the code generator will use
- Design the database schema
- Define API design conventions
- Document key design decisions with rationale"""


class ArchitectAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            name="Architect",
            description="Designs system architecture and complete project structure",
        )

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        self._log_step("Designing architecture...")

        specification = state.get("specification") or {}

        # Incorporate revision feedback if present
        all_feedback: list[dict] = state.get("human_feedback", [])
        arch_feedback = [
            fb for fb in all_feedback
            if fb.get("step") == "architecture_design"
            and fb.get("action") == "modify"
        ]
        feedback_context = ""
        if arch_feedback:
            latest = arch_feedback[-1]
            feedback_context = (
                f"\n\n── Human Reviewer Feedback (MUST be incorporated) ──\n"
                f"{latest.get('feedback', '')}\n"
                f"── End of feedback ──"
            )

        user_message = self._build_user_message(specification, feedback_context)

        architecture = await self._invoke_llm_json(
            system_prompt=_SYSTEM_PROMPT,
            user_message=user_message,
            include_directive=True,
            state=state
        )

        files_count = len(architecture.get("files_to_generate", []))
        self._log_step(
            f"Architecture complete — {files_count} files planned",
            {"files_to_generate": files_count},
        )

        return {
            **state,
            "architecture": architecture,
            "current_step": "architecture_design",
        }

    def _build_user_message(
        self, specification: dict[str, Any], feedback_context: str
    ) -> str:
        schema = json.dumps(
            {
                "architecture_pattern": "string — e.g. layered, hexagonal, MVC",
                "design_decisions": [
                    {
                        "decision": "string",
                        "rationale": "string",
                        "alternatives": ["string"],
                    }
                ],
                "components": [
                    {
                        "name": "string",
                        "layer": "presentation | application | domain | infrastructure",
                        "responsibility": "string",
                        "dependencies": ["string"],
                        "files": ["string — file paths"],
                    }
                ],
                "database_schema": {
                    "type": "postgresql | mysql | mongodb | sqlite",
                    "tables": [
                        {
                            "name": "string",
                            "columns": [
                                {
                                    "name": "string",
                                    "type": "string",
                                    "constraints": ["string"],
                                }
                            ],
                            "indexes": ["string"],
                            "foreign_keys": ["string"],
                        }
                    ],
                },
                "api_design": {
                    "style": "REST | GraphQL | gRPC",
                    "versioning": "string",
                    "authentication": "string",
                    "base_url": "/api/v1",
                },
                "key_patterns": ["string — design patterns in use"],
                "security_considerations": ["string"],
                "scalability_notes": ["string"],
                "files_to_generate": [
                    {
                        "path": "string — relative file path",
                        "description": "string — what this file does",
                        "component": "string — which component owns this",
                        "priority": 1,
                        "dependencies": ["string — other files this depends on"],
                    }
                ],
            },
            indent=2,
        )

        return (
            f"Design a comprehensive system architecture based on this specification.\n\n"
            f"**Specification:**\n"
            f"```json\n{json.dumps(specification, indent=2)[:6000]}\n```"
            f"{feedback_context}\n\n"
            f"Return a JSON object matching this exact schema:\n{schema}\n\n"
            "Ensure files_to_generate is complete and ordered by priority (1 = highest). "
            "Include ALL files needed for a production-ready project: "
            "source files, tests, configuration, migrations, Docker files, CI/CD, README."
        )
