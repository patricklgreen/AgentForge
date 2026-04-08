import asyncio
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are an elite Senior Software Engineer who writes \
production-quality code.

Your code follows:
- SOLID principles and clean code practices
- Comprehensive error handling with meaningful messages
- Type safety (type hints / annotations throughout)
- Security best practices (input validation, no hardcoded secrets)
- Performance optimisation (avoid N+1, use caching appropriately)
- Proper structured logging and observability
- Clear, descriptive naming conventions
- Comprehensive docstrings / JSDoc / JavaDoc

You write code that is ready to ship to production without modification.
Include all necessary imports and dependencies.

IMPORTANT: Keep files concise and focused. If a file would be very large (>2000 lines), 
break it into smaller, well-organized modules or use appropriate abstractions.

Output ONLY the raw file content — no markdown fences, no explanation."""


class CodeGeneratorAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            name="CodeGenerator",
            description="Generates production-quality source code for all project files",
        )

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        self._log_step("Starting code generation...")

        specification = state.get("specification") or {}
        architecture  = state.get("architecture") or {}
        files_to_generate: list[dict] = architecture.get("files_to_generate", [])

        # Incorporate revision feedback if present
        all_feedback: list[dict] = state.get("human_feedback", [])
        code_feedback = [
            fb for fb in all_feedback
            if fb.get("step") == "code_review"
            and fb.get("action") == "modify"
        ]
        feedback_context = ""
        if code_feedback:
            latest = code_feedback[-1]
            feedback_context = (
                f"\n\nHuman Code Review Feedback (incorporate in this generation):\n"
                f"{latest.get('feedback', '')}\n"
                f"Specific modifications: {json.dumps(latest.get('modifications', {}))}"
            )

        # Group files by priority for parallel execution within each group
        priority_groups = self._group_by_priority(files_to_generate)
        code_files: list[dict] = []
        context: list[dict] = []  # Accumulates as groups complete
        
        # Add semaphore to limit concurrent Bedrock requests and avoid throttling
        # Using 1 concurrent request for Opus to avoid overwhelming and ensure quality
        semaphore = asyncio.Semaphore(1)

        for group in priority_groups:
            group_size = len(group)
            self._log_step(
                f"Generating priority group of {group_size} file(s): "
                f"{[f['path'] for f in group]}"
            )

            if group_size == 1:
                result = await self._generate_file(
                    group[0], specification, architecture, context, feedback_context
                )
                if result:
                    code_files.append(result)
                    context.append(
                        {"path": result["path"], "description": group[0].get("description", "")}
                    )
            else:
                # Use semaphore to limit concurrent requests and avoid guardrail throttling
                async def generate_with_semaphore(file_info):
                    async with semaphore:
                        return await self._generate_file(
                            file_info, specification, architecture, context, feedback_context
                        )
                
                tasks = [generate_with_semaphore(f) for f in group]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for file_info, result in zip(group, results):
                    if isinstance(result, Exception):
                        logger.error(
                            f"Failed to generate {file_info['path']}: {result}"
                        )
                        continue
                    if result:
                        code_files.append(result)  # type: ignore[arg-type]
                        context.append(
                            {
                                "path": result["path"],  # type: ignore[index]
                                "description": file_info.get("description", ""),
                            }
                        )

        self._log_step(
            f"Code generation complete — {len(code_files)} files generated"
        )

        return {
            **state,
            "code_files":  code_files,
            "current_step": "code_generation",
        }

    async def _generate_file(
        self,
        file_info:       dict,
        specification:   dict,
        architecture:    dict,
        context:         list[dict],
        feedback_context: str = "",
    ) -> dict | None:
        file_path   = file_info.get("path", "")
        description = file_info.get("description", "")
        component   = file_info.get("component", "")

        if not file_path:
            return None

        tech_stack_str = json.dumps(
            specification.get("tech_stack", {}), indent=2
        )
        data_models_str = json.dumps(
            specification.get("data_models", [])[:10], indent=2
        )
        endpoints_str = json.dumps(
            specification.get("api_endpoints", [])[:20], indent=2
        )
        context_paths = [c["path"] for c in context[:20]]

        user_message = (
            f"Generate the file `{file_path}` for the following project.\n\n"
            f"**Project:** {specification.get('project_name', 'Application')}\n"
            f"**Language:** {specification.get('target_language', 'Python')}\n"
            f"**Framework:** {specification.get('target_framework', '')}\n"
            f"**Architecture Pattern:** {architecture.get('architecture_pattern', '')}\n"
            f"**Component:** {component}\n"
            f"**File Description:** {description}\n"
            f"**Dependencies on:** {file_info.get('dependencies', [])}\n\n"
            f"**Tech Stack:**\n{tech_stack_str}\n\n"
            f"**Data Models:**\n{data_models_str}\n\n"
            f"**API Endpoints (if applicable):**\n{endpoints_str}\n\n"
            f"**Already generated files (for import context):**\n"
            f"{json.dumps(context_paths)}\n\n"
            f"**Functional Requirements:**\n"
            f"{json.dumps(specification.get('functional_requirements', [])[:10], indent=2)}"
            f"{feedback_context}\n\n"
            "Output ONLY the raw file content for this single file. "
            "No markdown fences. No explanation. No preamble."
        )

        try:
            content = await self._invoke_llm(
                system_prompt=_SYSTEM_PROMPT,
                user_message=user_message,
                use_fast_model=False,  # Use Opus for better code generation and higher token limit
            )
            return {
                "path":        file_path,
                "content":     content,
                "description": description,
                "component":   component,
                "language":    self._detect_language(file_path),
            }
        except Exception as exc:
            logger.error(f"Failed to generate {file_path}: {exc}", exc_info=True)
            return None

    @staticmethod
    def _group_by_priority(files: list[dict]) -> list[list[dict]]:
        """Group files by priority for parallel generation within each group."""
        groups: dict[int, list[dict]] = defaultdict(list)
        for f in files:
            groups[f.get("priority", 99)].append(f)
        return [groups[k] for k in sorted(groups.keys())]

    @staticmethod
    def _detect_language(file_path: str) -> str:
        ext_map: dict[str, str] = {
            ".py":    "python",
            ".ts":    "typescript",
            ".tsx":   "typescript",
            ".js":    "javascript",
            ".jsx":   "javascript",
            ".java":  "java",
            ".go":    "go",
            ".rs":    "rust",
            ".rb":    "ruby",
            ".cs":    "csharp",
            ".cpp":   "cpp",
            ".c":     "c",
            ".kt":    "kotlin",
            ".swift": "swift",
            ".tf":    "terraform",
            ".yaml":  "yaml",
            ".yml":   "yaml",
            ".json":  "json",
            ".md":    "markdown",
            ".sh":    "bash",
            ".sql":   "sql",
            ".html":  "html",
            ".css":   "css",
        }
        ext = Path(file_path).suffix.lower()
        if file_path.lower() in ("dockerfile", "makefile"):
            return file_path.lower()
        return ext_map.get(ext, "plaintext")
