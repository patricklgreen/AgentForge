import json
from typing import Any

from app.agents.base import BaseAgent

_SYSTEM_PROMPT = """You are a Principal Engineer conducting a thorough code review.

You review code for:
1. Correctness and logic errors
2. Security vulnerabilities (OWASP Top 10, injection, auth bypass, SSRF, etc.)
3. Performance issues (N+1 queries, missing indexes, unbounded loops)
4. Code quality (SOLID principles, DRY, clear naming, clean functions)
5. Error handling completeness (are all exceptions caught? logged?)
6. Test coverage adequacy (are edge cases tested?)
7. Documentation completeness (public API documented?)
8. Dependency management (no pinned-but-vulnerable versions)
9. Potential race conditions or concurrency bugs
10. Compliance with the project's specified requirements

Be specific, actionable, and constructive. Cite file paths and describe fixes."""


class CodeReviewerAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            name="CodeReviewer",
            description="Reviews code for quality, security, and correctness",
        )

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        self._log_step("Starting automated code review...")

        specification      = state.get("specification") or {}
        code_files         = state.get("code_files", [])
        test_files         = state.get("test_files", [])
        validation_results = state.get("validation_results", [])

        review = await self._perform_review(
            specification=specification,
            code_files=code_files,
            test_files=test_files,
            validation_results=validation_results,
        )

        score   = review.get("overall_score", 0)
        issues  = review.get("total_issues", 0)
        critical = len(review.get("critical_issues", []))
        self._log_step(
            f"Review complete — Score: {score}/100 | "
            f"Total issues: {issues} ({critical} critical)"
        )

        return {
            **state,
            "review_comments": review,
            "current_step":    "code_review",
        }

    async def _perform_review(
        self,
        specification:     dict,
        code_files:        list[dict],
        test_files:        list[dict],
        validation_results: list[dict],
    ) -> dict:
        # Summarise validation results for the review context
        auto_fixed = [r for r in validation_results if r.get("was_fixed")]
        still_broken = [r for r in validation_results if r.get("has_errors") and not r.get("was_fixed")]
        validation_ctx = ""
        if auto_fixed or still_broken:
            validation_ctx = (
                f"\n**Validation Results:**\n"
                f"- {len(auto_fixed)} file(s) were auto-corrected by the validation agent\n"
                f"- {len(still_broken)} file(s) still have unresolved validation issues: "
                f"{[r['path'] for r in still_broken]}\n\n"
                "Do NOT penalise files for issues that were already auto-fixed. "
                "DO flag the unresolved validation issues as warnings."
            )

        # Trim code to avoid token limits while preserving most important sections
        code_summary = []
        for f in code_files:
            content = f.get("content", "")
            code_summary.append({
                "path":    f["path"],
                "content": content[:2500] + ("..." if len(content) > 2500 else ""),
            })

        user_message = (
            f"Perform a comprehensive code review for this project.\n\n"
            f"**Project:** {specification.get('project_name')}\n"
            f"**Language:** {specification.get('target_language')}\n"
            f"**Framework:** {specification.get('target_framework')}\n"
            f"{validation_ctx}\n"
            f"**Non-Functional Requirements:**\n"
            f"{json.dumps(specification.get('non_functional_requirements', []), indent=2)[:2000]}\n\n"
            f"**Code Files ({len(code_files)} total):**\n"
            f"{json.dumps(code_summary, indent=2)[:8000]}\n\n"
            f"**Test Files:**\n"
            f"{json.dumps([{'path': f['path'], 'type': f.get('type')} for f in test_files])}\n\n"
            "Return JSON with this exact structure:\n"
            "{\n"
            '  "overall_score": 0-100,\n'
            '  "total_issues": int,\n'
            '  "summary": "string — 2-3 sentence overall assessment",\n'
            '  "critical_issues": [\n'
            '    {"file": "str", "line_hint": "str", "category": "security|correctness|performance", '
            '"description": "str", "suggestion": "str"}\n'
            "  ],\n"
            '  "warnings": [\n'
            '    {"file": "str", "category": "quality|maintainability|testing", '
            '"description": "str", "suggestion": "str"}\n'
            "  ],\n"
            '  "improvements": [\n'
            '    {"file": "str", "category": "str", "description": "str", "benefit": "str"}\n'
            "  ],\n"
            '  "security_assessment": {"score": 0-100, "vulnerabilities": [], "recommendations": []},\n'
            '  "test_coverage_assessment": {"estimated_coverage": 0-100, "missing_tests": [], '
            '"recommendations": []},\n'
            '  "approved": true|false\n'
            "}"
        )

        return await self._invoke_llm_json(
            system_prompt=_SYSTEM_PROMPT,
            user_message=user_message,
            include_directive=True,
            state={
                "specification": specification,
                "requirements": "Review code against directive standards"
            }
        )
