import asyncio
import json
from pathlib import Path
from typing import Any

from app.agents.base import BaseAgent

_SYSTEM_PROMPT = """You are a Senior QA Engineer and Test Automation Expert who \
writes comprehensive, production-grade test suites.

You follow testing best practices:
- AAA pattern (Arrange, Act, Assert)
- Test isolation and independence — each test sets up its own state
- Descriptive test names that document behaviour: test_should_return_404_when_user_not_found
- Edge cases: empty input, nulls, max values, concurrent access, invalid formats
- Mock external dependencies cleanly (DB, HTTP, file system, queues)
- Target ≥90% code coverage for every source file
- Property-based testing for complex domain logic
- Integration tests for critical paths (API endpoints, DB operations)
- Performance tests for operations with SLA requirements

Your tests serve as living documentation of the system's behaviour."""


class TestWriterAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            name="TestWriter",
            description="Writes comprehensive test suites targeting ≥90% coverage",
        )

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        self._log_step("Writing test suite...")

        specification = state.get("specification") or {}
        code_files    = state.get("code_files", [])
        architecture  = state.get("architecture") or {}
        validation_results = state.get("validation_results", [])

        # Build a map of paths that were auto-fixed so tests focus on real behaviour
        auto_fixed_paths = {
            r["path"] for r in validation_results if r.get("was_fixed")
        }

        test_files: list[dict] = []

        # Add semaphore for concurrent test generation (matching CodeGenerator)
        # Using same aggressive concurrency that worked for code generation
        semaphore = asyncio.Semaphore(20)

        # Process unit tests and integration tests concurrently
        async def generate_unit_tests():
            # Unit tests for each source file - processed concurrently
            async def generate_test_with_semaphore(code_file):
                async with semaphore:
                    if self._should_test(code_file["path"]):
                        return await self._generate_unit_test(
                            code_file=code_file,
                            specification=specification,
                            all_code_files=code_files,
                            was_auto_fixed=code_file["path"] in auto_fixed_paths,
                        )
                    return None
            
            # Process all test files concurrently
            tasks = [generate_test_with_semaphore(code_file) for code_file in code_files]
            self.logger.info(f"🔄 Generating unit tests for {len(tasks)} files concurrently")
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Collect successful test results
            unit_tests = []
            for code_file, result in zip(code_files, results):
                if isinstance(result, Exception):
                    self.logger.error(f"Failed to generate test for {code_file['path']}: {result}")
                    continue
                if result:
                    unit_tests.append(result)
            
            return unit_tests

        async def generate_integration_tests():
            # Integration tests for API layer
            self.logger.info("🔄 Generating integration tests")
            return await self._generate_integration_tests(
                specification=specification,
                code_files=code_files,
            )

        # Run unit tests and integration tests in parallel
        self.logger.info("🔄 Starting concurrent test generation (unit + integration)")
        unit_tests, integration_tests = await asyncio.gather(
            generate_unit_tests(),
            generate_integration_tests(),
            return_exceptions=True
        )
        
        # Handle any errors
        if isinstance(unit_tests, Exception):
            self.logger.error(f"Unit test generation failed: {unit_tests}")
            unit_tests = []
        if isinstance(integration_tests, Exception):
            self.logger.error(f"Integration test generation failed: {integration_tests}")  
            integration_tests = []
        
        # Combine all tests
        test_files.extend(unit_tests)
        test_files.extend(integration_tests)

        # Test configuration files
        test_configs = self._generate_test_config(specification)
        test_files.extend(test_configs)

        self._log_step(
            f"Test generation complete — {len(test_files)} test files"
        )

        return {
            **state,
            "test_files":   test_files,
            "current_step": "test_writing",
        }

    async def _generate_unit_test(
        self,
        code_file:      dict,
        specification:  dict,
        all_code_files: list[dict],
        was_auto_fixed: bool = False,
    ) -> dict:
        language  = specification.get("target_language", "Python")
        test_path = self._get_test_path(code_file["path"], language)

        fixed_note = (
            "\nNote: This file was automatically corrected by the validation agent. "
            "Ensure tests cover the corrected behaviour."
            if was_auto_fixed else ""
        )

        user_message = (
            f"Write a comprehensive unit test file for `{code_file['path']}`.\n\n"
            f"**Language:** {language}\n"
            f"**Framework:** {specification.get('target_framework', '')}\n"
            f"**Test file path:** {test_path}\n"
            f"{fixed_note}\n\n"
            f"**Source code to test:**\n"
            f"```\n{code_file['content'][:8000]}\n```\n\n"
            f"**Data models for context:**\n"
            f"{json.dumps(specification.get('data_models', []), indent=2)[:2000]}\n\n"
            "Requirements:\n"
            "1. Achieve ≥90% line and branch coverage for this file\n"
            "2. Test every public function / method / class\n"
            "3. Test happy paths AND edge cases (empty input, null, max values, errors)\n"
            "4. Mock all external dependencies (DB, HTTP, file system, queues)\n"
            "5. Follow AAA (Arrange-Act-Assert) pattern\n"
            "6. Use descriptive test names: test_should__when_\n"
            "7. Include docstrings/comments explaining non-obvious test setup\n\n"
            "Output ONLY the raw test file content. No markdown fences. No explanation."
        )

        content = await self._invoke_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_message=user_message,
        )

        return {
            "path":        test_path,
            "content":     content,
            "source_file": code_file["path"],
            "language":    code_file.get("language", "plaintext"),
            "type":        "unit_test",
        }

    async def _generate_integration_tests(
        self,
        specification: dict,
        code_files:    list[dict],
    ) -> list[dict]:
        language        = specification.get("target_language", "Python")
        api_endpoints   = specification.get("api_endpoints", [])

        if not api_endpoints:
            return []

        user_message = (
            f"Write comprehensive integration tests for the API layer.\n\n"
            f"**Language:** {language}\n"
            f"**Framework:** {specification.get('target_framework', '')}\n\n"
            f"**API Endpoints to test:**\n"
            f"{json.dumps(api_endpoints, indent=2)[:4000]}\n\n"
            f"**Data Models:**\n"
            f"{json.dumps(specification.get('data_models', []), indent=2)[:2000]}\n\n"
            "Write integration tests that:\n"
            "1. Test every API endpoint (happy path + all error cases)\n"
            "2. Test authentication and authorization rules\n"
            "3. Test request validation (invalid data, missing fields)\n"
            "4. Test database interactions end-to-end\n"
            "5. Use proper test setup and teardown (clean DB state per test)\n"
            "6. Test concurrent request scenarios where relevant\n\n"
            "Output ONLY the raw test file content."
        )

        content = await self._invoke_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_message=user_message,
        )

        lang_lower = language.lower()
        if lang_lower == "python":
            test_path = "tests/integration/test_api.py"
        elif lang_lower in ("typescript", "javascript"):
            test_path = "__tests__/integration/api.test.ts"
        elif lang_lower == "java":
            test_path = "src/test/java/integration/ApiIntegrationTest.java"
        elif lang_lower == "csharp":
            test_path = "tests/Integration/ApiIntegrationTests.cs"
        else:
            test_path = "tests/integration/test_api.py"

        return [
            {
                "path":     test_path,
                "content":  content,
                "language": code_files[0].get("language", "python") if code_files else "python",
                "type":     "integration_test",
            }
        ]

    @staticmethod
    def _generate_test_config(specification: dict) -> list[dict]:
        language = specification.get("target_language", "Python").lower()
        configs: list[dict] = []

        if language == "python":
            configs.append({
                "path": "pytest.ini",
                "content": (
                    "[pytest]\n"
                    "asyncio_mode = auto\n"
                    "testpaths = tests\n"
                    "python_files = test_*.py\n"
                    "python_classes = Test*\n"
                    "python_functions = test_*\n"
                    "addopts =\n"
                    "    --cov=app\n"
                    "    --cov-report=html\n"
                    "    --cov-report=term-missing\n"
                    "    --cov-fail-under=90\n"
                    "    -v\n"
                ),
                "language": "ini",
                "type":     "config",
            })
            configs.append({
                "path": ".coveragerc",
                "content": (
                    "[run]\n"
                    "source = app\n"
                    "omit =\n"
                    "    */tests/*\n"
                    "    */migrations/*\n"
                    "    */__init__.py\n\n"
                    "[report]\n"
                    "show_missing = True\n"
                    "fail_under = 90\n"
                ),
                "language": "ini",
                "type":     "config",
            })
        elif language in ("typescript", "javascript"):
            configs.append({
                "path": "jest.config.ts",
                "content": (
                    "import type { Config } from 'jest';\n\n"
                    "const config: Config = {\n"
                    "  preset: 'ts-jest',\n"
                    "  testEnvironment: 'node',\n"
                    "  coverageThreshold: {\n"
                    "    global: { lines: 90, branches: 85, functions: 90, statements: 90 },\n"
                    "  },\n"
                    "  collectCoverageFrom: ['src/**/*.ts', '!src/**/*.d.ts'],\n"
                    "};\n\nexport default config;\n"
                ),
                "language": "typescript",
                "type":     "config",
            })

        return configs

    @staticmethod
    def _should_test(file_path: str) -> bool:
        skip_patterns = frozenset([
            "test_", "__init__", "migrations/", "alembic/", "config.",
            "settings.", ".md", ".yaml", ".yml", ".json", "dockerfile",
            "makefile", ".sh", ".tf", ".hcl", "__snapshots__",
        ])
        path_lower = file_path.lower()
        return not any(pattern in path_lower for pattern in skip_patterns)

    @staticmethod
    def _get_test_path(source_path: str, language: str) -> str:
        p = Path(source_path)
        lang = language.lower()

        if lang == "python":
            return f"tests/unit/test_{p.name}"
        elif lang in ("typescript", "javascript"):
            return str(p.parent / f"{p.stem}.test{p.suffix}")
        elif lang == "java":
            return str(source_path).replace("src/main", "src/test").replace(
                ".java", "Test.java"
            )
        elif lang == "csharp":
            return str(p.parent / f"{p.stem}Tests{p.suffix}")
        elif lang == "go":
            return str(p.parent / f"{p.stem}_test{p.suffix}")
        else:
            return f"tests/test_{p.name}"
