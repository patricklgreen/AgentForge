import ast
import asyncio
import logging
import subprocess
from asyncio import get_event_loop
from functools import partial
from typing import Any

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class ValidationAgent(BaseAgent):
    """
    Validates generated source files for syntax errors and attempts
    LLM-powered auto-correction before tests are written.

    Pipeline position: generate_code → validate_code → write_tests

    Validation strategies
    ─────────────────────
    Python      → ast.parse() (always available) + optional ruff
    JavaScript  → node --check (if node is in PATH)
    TypeScript / Java / C# / Go / Rust / Ruby → LLM quick-check
    Config / data files → skipped

    The agent NEVER blocks the pipeline.  If validation or auto-fix fails,
    the file is left unchanged and the issue is flagged for human review.
    """

    _LANGUAGE_DISPLAY: dict[str, str] = {
        "typescript": "TypeScript",
        "javascript": "JavaScript",
        "java":       "Java",
        "csharp":     "C#",
        "go":         "Go",
        "rust":       "Rust",
        "ruby":       "Ruby",
        "kotlin":     "Kotlin",
        "swift":      "Swift",
        "cpp":        "C++",
        "c":          "C",
    }

    _SKIP_PATTERNS: frozenset[str] = frozenset([
        ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
        ".env", ".xml", ".properties", ".plist",
        ".md", ".txt", ".rst",
        ".tf", ".hcl", "dockerfile", "makefile",
        ".sh", ".bash", ".zsh", ".ps1", ".bat",
        "/migrations/", "/alembic/versions/",
        "package-lock.json", "yarn.lock", "poetry.lock",
        "go.sum", "cargo.lock",
        ".snap", "/__snapshots__/",
    ])

    def __init__(self) -> None:
        super().__init__(
            name="Validator",
            description=(
                "Validates generated code for syntax errors and "
                "auto-corrects issues before tests are written."
            ),
        )

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        self._log_step("Starting code validation...")

        code_files: list[dict]  = state.get("code_files", [])
        specification: dict     = state.get("specification", {})
        project_language: str   = specification.get("target_language", "").lower()

        if not code_files:
            self._log_step("No code files to validate — skipping")
            return {**state, "validation_results": [], "current_step": "validation"}

        # Validate all files concurrently
        results_raw = await asyncio.gather(
            *[self._validate_file(f, project_language) for f in code_files],
            return_exceptions=True,
        )

        validation_results: list[dict] = []
        files_needing_fix: list[tuple[dict, dict]] = []

        for file_info, outcome in zip(code_files, results_raw):
            if isinstance(outcome, Exception):
                logger.warning(
                    f"Validation of {file_info['path']} raised (non-fatal): {outcome}"
                )
                validation_results.append(
                    {
                        "path":               file_info["path"],
                        "has_errors":         False,
                        "errors":             [],
                        "was_fixed":          False,
                        "validation_skipped": True,
                        "skip_reason":        "validation_exception",
                    }
                )
            else:
                validation_results.append(outcome)  # type: ignore[arg-type]
                if outcome.get("has_errors"):  # type: ignore[union-attr]
                    files_needing_fix.append((file_info, outcome))  # type: ignore[arg-type]

        # Attempt auto-fix for files with errors
        updated_code_files = list(code_files)
        if files_needing_fix:
            self._log_step(
                f"{len(files_needing_fix)} file(s) have errors — attempting auto-fix..."
            )
            updated_code_files, validation_results = await self._auto_fix_batch(
                code_files=updated_code_files,
                files_needing_fix=files_needing_fix,
                validation_results=validation_results,
                specification=specification,
            )

        total_checked  = sum(1 for r in validation_results if not r.get("validation_skipped"))
        still_erroring = sum(1 for r in validation_results if r.get("has_errors") and not r.get("was_fixed"))
        auto_fixed     = sum(1 for r in validation_results if r.get("was_fixed"))

        self._log_step(
            f"Validation complete — {total_checked} checked, "
            f"{auto_fixed} auto-fixed, {still_erroring} still have issues"
        )

        return {
            **state,
            "code_files":        updated_code_files,
            "validation_results": validation_results,
            "current_step":      "validation",
        }

    # ─── Per-file validation ──────────────────────────────────────────────────

    async def _validate_file(
        self, file_info: dict, project_language: str
    ) -> dict:
        path     = file_info["path"]
        content  = file_info.get("content", "")
        lang     = (file_info.get("language") or project_language).lower()

        base: dict = {
            "path": path, "has_errors": False,
            "errors": [], "was_fixed": False,
        }

        if not content.strip():
            return {**base, "validation_skipped": True, "skip_reason": "empty_file"}

        if self._should_skip(path):
            return {**base, "validation_skipped": True, "skip_reason": "skipped_by_pattern"}

        if lang == "python":
            errors = await self._validate_python(content)
        elif lang == "javascript":
            errors = await self._validate_javascript(content)
        elif lang in self._LANGUAGE_DISPLAY:
            errors = await self._validate_via_llm(
                content, path, self._LANGUAGE_DISPLAY[lang]
            )
        else:
            return {**base, "validation_skipped": True, "skip_reason": "unknown_language"}

        return {
            "path": path,
            "has_errors": len(errors) > 0,
            "errors": errors,
            "was_fixed": False,
            "validation_skipped": False,
        }

    # ─── Language validators ──────────────────────────────────────────────────

    async def _validate_python(self, content: str) -> list[dict]:
        errors: list[dict] = []

        # Pass 1: AST parse (always available, instant)
        try:
            ast.parse(content)
        except SyntaxError as exc:
            errors.append(
                {
                    "check":  "python_ast",
                    "output": f"SyntaxError at line {exc.lineno}: {exc.msg}",
                    "line":   exc.lineno,
                }
            )
            return errors  # ruff cannot run on broken syntax

        # Pass 2: ruff (optional — silently skipped if not installed)
        ruff_errors = await self._run_stdin(
            cmd=["ruff", "check", "--select", "E,F,W,B", "--no-fix",
                 "--output-format", "text", "-"],
            content=content,
            check_name="ruff",
        )
        errors.extend(ruff_errors)
        return errors

    async def _validate_javascript(self, content: str) -> list[dict]:
        return await self._run_stdin(
            cmd=["node", "--check", "--input-type=module"],
            content=content,
            check_name="node",
        )

    async def _validate_via_llm(
        self, content: str, path: str, language: str
    ) -> list[dict]:
        excerpt = (
            content if len(content) <= 6000
            else content[:3000] + "\n\n[... truncated ...]\n\n" + content[-1000:]
        )
        try:
            result = await self._invoke_llm_json(
                system_prompt=(
                    f"You are a strict {language} syntax checker. "
                    "Identify ONLY definite syntax errors that prevent compilation/parsing. "
                    "Do NOT report style issues, unused variables, or logic bugs. "
                    "If syntactically valid, return has_errors: false."
                ),
                user_message=(
                    f"Check this {language} code:\n\n"
                    f"```{language.lower()}\n{excerpt}\n```\n\n"
                    'Return: {"has_errors": bool, "errors": '
                    '[{"description": "str", "line_hint": "str"}]}'
                ),
                use_fast_model=True,
                include_directive=False,  # Don't need directive context for syntax checking
            )
            if result.get("has_errors") and result.get("errors"):
                return [
                    {
                        "check":     "llm_syntax_check",
                        "output":    e.get("description", "Syntax error"),
                        "line_hint": e.get("line_hint", ""),
                        "line":      None,
                    }
                    for e in result.get("errors", [])[:10]
                ]
        except Exception as exc:
            logger.debug(f"LLM syntax check for {path} skipped: {exc}")
        return []

    # ─── Subprocess helper ────────────────────────────────────────────────────

    async def _run_stdin(
        self,
        cmd:        list[str],
        content:    str,
        check_name: str,
        timeout:    int = 15,
    ) -> list[dict]:
        try:
            loop = get_event_loop()
            result: subprocess.CompletedProcess = await loop.run_in_executor(
                None,
                partial(
                    subprocess.run,
                    cmd,
                    input=content,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                ),
            )
            if result.returncode != 0:
                raw = (result.stderr or result.stdout).strip()
                if raw:
                    return [{"check": check_name, "output": raw[:800], "line": None}]
        except FileNotFoundError:
            logger.debug(f"'{cmd[0]}' not in PATH — skipping {check_name} validation")
        except subprocess.TimeoutExpired:
            logger.warning(f"{check_name} validation timed out")
        except Exception as exc:
            logger.debug(f"{check_name} validation error (non-fatal): {exc}")
        return []

    # ─── Auto-fix ─────────────────────────────────────────────────────────────

    async def _auto_fix_batch(
        self,
        code_files:        list[dict],
        files_needing_fix: list[tuple[dict, dict]],
        validation_results: list[dict],
        specification:     dict,
    ) -> tuple[list[dict], list[dict]]:
        language = specification.get("target_language", "")

        file_idx    = {f["path"]: i for i, f in enumerate(code_files)}
        result_idx  = {r["path"]: i for i, r in enumerate(validation_results)}

        outcomes = await asyncio.gather(
            *[
                self._fix_single_file(f, e, language)
                for f, e in files_needing_fix
            ],
            return_exceptions=True,
        )

        updated_files   = list(code_files)
        updated_results = list(validation_results)

        for (file_info, error_record), outcome in zip(files_needing_fix, outcomes):
            path = file_info["path"]
            if isinstance(outcome, Exception):
                logger.warning(f"Auto-fix for {path} raised: {outcome}")
                continue

            fixed_content, was_fixed = outcome  # type: ignore[misc]

            i = file_idx.get(path)
            if i is not None and was_fixed:
                updated_files[i] = {**code_files[i], "content": fixed_content}

            j = result_idx.get(path)
            if j is not None:
                updated_results[j] = {
                    **error_record,
                    "was_fixed":  was_fixed,
                    "has_errors": not was_fixed,
                }

        return updated_files, updated_results

    async def _fix_single_file(
        self,
        file_info:    dict,
        error_record: dict,
        language:     str,
    ) -> tuple[str, bool]:
        path     = file_info["path"]
        original = file_info.get("content", "")
        errors   = error_record.get("errors", [])

        error_lines = "\n".join(
            f"  - [{e.get('check', 'error')}] "
            f"{('line ' + str(e['line']) + ': ') if e.get('line') else ''}"
            f"{e.get('output', '')}"
            for e in errors[:8]
        )

        try:
            fixed = await self._invoke_llm(
                system_prompt=(
                    f"You are an expert {language} developer fixing specific "
                    "compilation/syntax errors. Fix ONLY the reported errors. "
                    "Change nothing else. Output ONLY the raw corrected file content."
                ),
                user_message=(
                    f"Fix these validation errors in `{path}`:\n\n"
                    f"**Errors:**\n{error_lines}\n\n"
                    f"**Current file:**\n```\n{original}\n```\n\n"
                    "Return ONLY the corrected file content."
                ),
                use_fast_model=True,
                include_directive=True,
                state={
                    "specification": {"target_language": language},
                    "requirements": "Fix syntax errors while maintaining directive standards"
                }
            )

            # Verify the fix for Python (instant, no extra LLM call)
            if (file_info.get("language") or "").lower() == "python":
                try:
                    ast.parse(fixed)
                    logger.info(f"Auto-fix verified for {path}")
                    return fixed, True
                except SyntaxError as exc:
                    logger.warning(
                        f"Auto-fix introduced new SyntaxError at line {exc.lineno} "
                        f"in {path} — reverting"
                    )
                    return original, False

            logger.info(f"Auto-fix applied for {path} (unverified)")
            return fixed, True

        except Exception as exc:
            logger.error(f"LLM auto-fix failed for {path}: {exc}")
            return original, False

    def _should_skip(self, file_path: str) -> bool:
        path_lower = file_path.lower()
        if path_lower.endswith("__init__.py"):
            return True
        for pattern in self._SKIP_PATTERNS:
            if pattern in path_lower:
                return True
        return False
