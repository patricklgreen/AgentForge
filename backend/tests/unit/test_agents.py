"""
Unit tests for all agent classes.
Each test uses mocked LLM/service calls — no real AWS calls.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def base_state(sample_specification, sample_architecture):
    return {
        "project_id":         "test-project-id",
        "run_id":             "test-run-id",
        "requirements": (
            "Build a RESTful API for an e-commerce platform with user auth, "
            "product catalog, shopping cart, and order processing."
        ),
        "target_language":    "Python",
        "target_framework":   "FastAPI",
        "specification":      sample_specification,
        "architecture":       sample_architecture,
        "code_files":         [],
        "test_files":         [],
        "review_comments":    None,
        "devops_files":       [],
        "documentation":      None,
        "human_feedback":     [],
        "current_step":       "starting",
        "error":              None,
        "validation_results": [],
        "quality_violations": [],
        "zip_url":            None,
    }


# ─── RequirementsAnalystAgent ─────────────────────────────────────────────────

class TestRequirementsAnalystAgent:
    @pytest.mark.asyncio
    async def test_execute_returns_specification(self, base_state):
        mock_spec = {
            "project_name": "ecommerce-api",
            "project_summary": "An e-commerce REST API",
            "target_language": "Python",
            "target_framework": "FastAPI",
            "functional_requirements": [
                {"id": "FR-001", "title": "Auth", "description": "JWT auth",
                 "priority": "must", "user_story": "", "acceptance_criteria": ["Can login"],
                 "affected_entities": []},
            ],
            "non_functional_requirements": [],
            "user_roles": [],
            "data_models": [],
            "api_endpoints": [],
            "integrations": [],
            "tech_stack": {"language": "Python", "framework": "FastAPI",
                           "database": "PostgreSQL", "cache": None, "auth": "JWT",
                           "testing": "pytest", "orm": "SQLAlchemy",
                           "task_queue": None, "search": None, "file_storage": None,
                           "observability": "structlog", "ci_cd": "GitHub Actions",
                           "containerisation": "Docker", "additional": []},
            "constraints": [], "assumptions": [], "open_questions": [],
            "out_of_scope": [], "glossary": [],
        }

        with patch("app.agents.requirements_analyst.bedrock_service") as mock_bedrock:
            mock_bedrock.invoke_with_json_output = AsyncMock(return_value=mock_spec)
            from app.agents.requirements_analyst import RequirementsAnalystAgent
            agent = RequirementsAnalystAgent()
            state = {**base_state, "specification": None, "target_framework": "FastAPI"}
            result = await agent.execute(state)

        assert result["specification"] is not None
        assert result["specification"]["project_name"] == "ecommerce-api"
        assert result["current_step"] == "requirements_analysis"

    @pytest.mark.asyncio
    async def test_execute_auto_selects_framework_from_profile(self, base_state):
        """When no framework is given, profile should auto-select one."""
        mock_spec = {
            "project_name": "test", "project_summary": "", "target_language": "Python",
            "target_framework": "FastAPI", "functional_requirements": [],
            "non_functional_requirements": [], "user_roles": [], "data_models": [],
            "api_endpoints": [], "integrations": [],
            "tech_stack": {"language": "Python", "framework": "FastAPI",
                           "database": "PostgreSQL", "testing": "pytest",
                           "orm": "SQLAlchemy", "ci_cd": "GitHub Actions",
                           "containerisation": "Docker", "observability": "structlog",
                           "cache": None, "auth": None, "task_queue": None,
                           "search": None, "file_storage": None, "additional": []},
            "constraints": [], "assumptions": [], "open_questions": [],
            "out_of_scope": [], "glossary": [],
        }
        state = {**base_state, "specification": None, "target_framework": ""}
        with patch("app.agents.requirements_analyst.bedrock_service") as mock_bedrock:
            mock_bedrock.invoke_with_json_output = AsyncMock(return_value=mock_spec)
            from app.agents.requirements_analyst import RequirementsAnalystAgent
            agent = RequirementsAnalystAgent()
            result = await agent.execute(state)

        # Should resolve a framework from the Python profile
        assert result["target_framework"] != ""

    @pytest.mark.asyncio
    async def test_execute_incorporates_human_feedback(self, base_state):
        """Feedback text should appear in the LLM call arguments."""
        state = {
            **base_state,
            "specification": None,
            "human_feedback": [
                {
                    "step":     "requirements_analysis",
                    "action":   "modify",
                    "feedback": "Add WebSocket real-time notifications",
                }
            ],
        }

        captured_message: list[str] = []

        async def capture_invoke(system_prompt, user_message, **kwargs):
            captured_message.append(user_message)
            return {
                "project_name": "test", "project_summary": "", "target_language": "Python",
                "target_framework": "FastAPI", "functional_requirements": [],
                "non_functional_requirements": [], "user_roles": [], "data_models": [],
                "api_endpoints": [], "integrations": [],
                "tech_stack": {"language": "Python", "framework": "FastAPI",
                               "database": "PostgreSQL", "testing": "pytest",
                               "orm": "SQLAlchemy", "ci_cd": "GitHub Actions",
                               "containerisation": "Docker", "observability": "structlog",
                               "cache": None, "auth": None, "task_queue": None,
                               "search": None, "file_storage": None, "additional": []},
                "constraints": [], "assumptions": [], "open_questions": [],
                "out_of_scope": [], "glossary": [],
            }

        with patch("app.agents.requirements_analyst.bedrock_service") as mock_bedrock:
            mock_bedrock.invoke_with_json_output = AsyncMock(side_effect=capture_invoke)
            from app.agents.requirements_analyst import RequirementsAnalystAgent
            agent = RequirementsAnalystAgent()
            await agent.execute(state)

        assert captured_message, "LLM was never called"
        assert "WebSocket" in captured_message[0]

    @pytest.mark.asyncio
    async def test_execute_raises_on_llm_failure(self, base_state):
        state = {**base_state, "specification": None}
        with patch("app.agents.requirements_analyst.bedrock_service") as mock_bedrock:
            mock_bedrock.invoke_with_json_output = AsyncMock(
                side_effect=Exception("Bedrock unavailable")
            )
            from app.agents.requirements_analyst import RequirementsAnalystAgent
            agent = RequirementsAnalystAgent()
            with pytest.raises(Exception, match="Bedrock unavailable"):
                await agent.execute(state)


# ─── ArchitectAgent ───────────────────────────────────────────────────────────

class TestArchitectAgent:
    @pytest.mark.asyncio
    async def test_execute_returns_architecture(self, base_state, sample_architecture):
        with patch("app.agents.architect.bedrock_service") as mock_bedrock:
            mock_bedrock.invoke_with_json_output = AsyncMock(return_value=sample_architecture)
            from app.agents.architect import ArchitectAgent
            agent = ArchitectAgent()
            result = await agent.execute(base_state)

        assert result["architecture"] is not None
        assert result["architecture"]["architecture_pattern"] == "layered"
        assert result["current_step"] == "architecture_design"

    @pytest.mark.asyncio
    async def test_execute_preserves_state_fields(self, base_state, sample_architecture):
        with patch("app.agents.architect.bedrock_service") as mock_bedrock:
            mock_bedrock.invoke_with_json_output = AsyncMock(return_value=sample_architecture)
            from app.agents.architect import ArchitectAgent
            agent = ArchitectAgent()
            result = await agent.execute(base_state)

        assert result["project_id"]   == base_state["project_id"]
        assert result["requirements"] == base_state["requirements"]
        assert result["specification"] is not None


# ─── CodeGeneratorAgent ───────────────────────────────────────────────────────

class TestCodeGeneratorAgent:
    @pytest.mark.asyncio
    async def test_generates_files_in_priority_order(self, base_state, sample_architecture):
        state = {
            **base_state,
            "architecture": {
                **sample_architecture,
                "files_to_generate": [
                    {"path": "app/routes.py",  "priority": 2, "description": "Routes",
                     "component": "api", "dependencies": []},
                    {"path": "app/main.py",    "priority": 1, "description": "Entry point",
                     "component": "api", "dependencies": []},
                    {"path": "app/models.py",  "priority": 3, "description": "Models",
                     "component": "domain", "dependencies": []},
                ],
            },
        }

        generated_order: list[str] = []

        async def mock_invoke(system_prompt, user_message, **kwargs):
            # Extract filename from prompt
            for line in user_message.split("\n"):
                if "Generate the file" in line and "`" in line:
                    path = line.split("`")[1]
                    generated_order.append(path)
            return "# generated code"

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="# generated code"))

        with patch("app.agents.code_generator.bedrock_service") as mock_bedrock:
            mock_bedrock.get_llm = MagicMock(return_value=mock_llm)
            mock_bedrock.get_fast_llm = MagicMock(return_value=mock_llm)
            from app.agents.code_generator import CodeGeneratorAgent
            agent = CodeGeneratorAgent()
            result = await agent.execute(state)

        assert len(result["code_files"]) == 3
        paths = [f["path"] for f in result["code_files"]]
        # Priority 1 must come before priority 2 and 3
        assert paths.index("app/main.py") < paths.index("app/routes.py")
        assert paths.index("app/routes.py") < paths.index("app/models.py")

    def test_detect_language_coverage(self):
        from app.agents.code_generator import CodeGeneratorAgent
        agent = CodeGeneratorAgent()

        cases = [
            ("app/main.py",          "python"),
            ("src/index.ts",         "typescript"),
            ("src/App.tsx",          "typescript"),
            ("index.js",             "javascript"),
            ("main.go",              "go"),
            ("Main.java",            "java"),
            ("program.cs",           "csharp"),
            ("main.rs",              "rust"),
            ("main.tf",              "terraform"),
            ("config.yaml",          "yaml"),
            ("config.yml",           "yaml"),
            ("data.json",            "json"),
            ("README.md",            "markdown"),
            ("deploy.sh",            "bash"),
            ("schema.sql",           "sql"),
            ("index.html",           "html"),
            ("styles.css",           "css"),
            ("unknown.xyz",          "plaintext"),
        ]
        for path, expected in cases:
            assert agent._detect_language(path) == expected, (
                f"Failed for {path}: expected {expected}"
            )

    @pytest.mark.asyncio
    async def test_skips_files_with_empty_path(self, base_state, sample_architecture):
        state = {
            **base_state,
            "architecture": {
                **sample_architecture,
                "files_to_generate": [
                    {"path": "",           "priority": 1, "description": "Empty path",
                     "component": "api", "dependencies": []},
                    {"path": "app/main.py", "priority": 1, "description": "Main",
                     "component": "api", "dependencies": []},
                ],
            },
        }
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="# code"))

        with patch("app.agents.code_generator.bedrock_service") as mock_bedrock:
            mock_bedrock.get_llm = MagicMock(return_value=mock_llm)
            mock_bedrock.get_fast_llm = MagicMock(return_value=mock_llm)
            from app.agents.code_generator import CodeGeneratorAgent
            agent = CodeGeneratorAgent()
            result = await agent.execute(state)

        # Only the non-empty path should be generated
        assert len(result["code_files"]) == 1
        assert result["code_files"][0]["path"] == "app/main.py"


# ─── ValidationAgent ──────────────────────────────────────────────────────────

class TestValidationAgent:
    @pytest.mark.asyncio
    async def test_validates_valid_python(self, base_state):
        state = {
            **base_state,
            "code_files": [
                {
                    "path":     "app/main.py",
                    "content":  "def hello():\n    return 'world'\n",
                    "language": "python",
                }
            ],
        }
        from app.agents.validation_agent import ValidationAgent
        agent = ValidationAgent()
        result = await agent.execute(state)

        results = result["validation_results"]
        assert len(results) == 1
        assert results[0]["has_errors"] is False
        assert results[0]["was_fixed"] is False

    @pytest.mark.asyncio
    async def test_detects_python_syntax_error(self, base_state):
        state = {
            **base_state,
            "code_files": [
                {
                    "path":     "app/broken.py",
                    "content":  "def broken(\n    return 'oops'\n",
                    "language": "python",
                }
            ],
        }

        async def mock_fix(*args, **kwargs):
            # Return syntactically valid fixed code
            return "def broken():\n    return 'oops'\n", True

        with patch("app.agents.validation_agent.ValidationAgent._fix_single_file",
                   new=mock_fix):
            from app.agents.validation_agent import ValidationAgent
            agent = ValidationAgent()
            result = await agent.execute(state)

        results = result["validation_results"]
        assert len(results) == 1
        # File had an error initially; after fix it should be resolved
        assert results[0]["was_fixed"] is True

    @pytest.mark.asyncio
    async def test_skips_config_files(self, base_state):
        state = {
            **base_state,
            "code_files": [
                {"path": "config.yaml",  "content": "key: value", "language": "yaml"},
                {"path": "README.md",    "content": "# Hello",    "language": "markdown"},
                {"path": ".env.example", "content": "KEY=value",  "language": "bash"},
            ],
        }
        from app.agents.validation_agent import ValidationAgent
        agent = ValidationAgent()
        result = await agent.execute(state)

        for r in result["validation_results"]:
            assert r["validation_skipped"] is True

    def test_should_skip_patterns(self):
        from app.agents.validation_agent import ValidationAgent
        agent = ValidationAgent()

        assert agent._should_skip("config.yaml")       is True
        assert agent._should_skip("README.md")         is True
        assert agent._should_skip("alembic/versions/001.py") is True
        assert agent._should_skip("app/__init__.py")   is True
        assert agent._should_skip("app/services/s3.py") is False
        assert agent._should_skip("app/main.py")       is False

    @pytest.mark.asyncio
    async def test_empty_code_files_returns_immediately(self, base_state):
        state = {**base_state, "code_files": []}
        from app.agents.validation_agent import ValidationAgent
        agent = ValidationAgent()
        result = await agent.execute(state)

        assert result["validation_results"] == []
        assert result["current_step"] == "validation"


# ─── TestWriterAgent ─────────────────────────────────────────────────────────

class TestTestWriterAgent:
    @pytest.mark.asyncio
    async def test_generates_test_files(self, base_state):
        state = {
            **base_state,
            "code_files": [
                {
                    "path":      "app/services/user_service.py",
                    "content":   "class UserService:\n    def create(self): pass\n",
                    "language":  "python",
                    "component": "service",
                }
            ],
            "validation_results": [],
        }

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=MagicMock(
                content="import pytest\n\ndef test_create_user():\n    pass\n"
            )
        )

        with patch("app.agents.test_writer.bedrock_service") as mock_bedrock:
            mock_bedrock.get_llm = MagicMock(return_value=mock_llm)
            mock_bedrock.get_fast_llm = MagicMock(return_value=mock_llm)
            from app.agents.test_writer import TestWriterAgent
            agent = TestWriterAgent()
            result = await agent.execute(state)

        assert len(result["test_files"]) > 0
        assert result["current_step"] == "test_writing"

    def test_should_test_filtering(self):
        from app.agents.test_writer import TestWriterAgent
        agent = TestWriterAgent()

        # Should generate tests for
        assert agent._should_test("app/services/user_service.py") is True
        assert agent._should_test("app/api/routes/users.py")      is True

        # Should NOT generate tests for
        assert agent._should_test("tests/test_user.py")           is False
        assert agent._should_test("alembic/versions/001.py")      is False
        assert agent._should_test("app/config.py")                is False
        assert agent._should_test("README.md")                    is False
        assert agent._should_test("docker-compose.yml")           is False
        assert agent._should_test("main.tf")                      is False

    def test_get_test_path_for_each_language(self):
        from app.agents.test_writer import TestWriterAgent
        agent = TestWriterAgent()

        assert "test_service.py" in agent._get_test_path(
            "app/services/service.py", "Python"
        )
        assert "service.test.ts" in agent._get_test_path(
            "src/services/service.ts", "TypeScript"
        )
        assert "ServiceTest.java" in agent._get_test_path(
            "src/main/java/Service.java", "Java"
        )
        assert "ServiceTests.cs" in agent._get_test_path(
            "src/Service.cs", "C#"
        )
        assert "service_test.go" in agent._get_test_path(
            "internal/service.go", "Go"
        )

    @pytest.mark.asyncio
    async def test_skips_integration_tests_when_no_endpoints(self, base_state):
        """No API endpoints in spec → no integration test file generated."""
        state = {
            **base_state,
            "specification": {**base_state["specification"], "api_endpoints": []},
            "code_files": [],
            "validation_results": [],
        }
        from app.agents.test_writer import TestWriterAgent
        agent = TestWriterAgent()

        with patch("app.agents.test_writer.bedrock_service"):
            result = await agent.execute(state)

        # Should still have config files but no integration test
        integration_tests = [
            f for f in result["test_files"]
            if f.get("type") == "integration_test"
        ]
        assert len(integration_tests) == 0


# ─── CodeReviewerAgent ────────────────────────────────────────────────────────

class TestCodeReviewerAgent:
    @pytest.mark.asyncio
    async def test_execute_returns_review_comments(self, base_state):
        state = {
            **base_state,
            "code_files": [
                {"path": "app/main.py",
                 "content": "from fastapi import FastAPI\napp = FastAPI()\n"}
            ],
            "test_files": [
                {"path": "tests/test_main.py",
                 "content": "def test_app(): pass\n",
                 "type": "unit_test"}
            ],
            "validation_results": [],
        }
        mock_review = {
            "overall_score":   85,
            "total_issues":    2,
            "summary":         "Good code quality overall.",
            "critical_issues": [],
            "warnings":        [
                {"file": "app/main.py", "category": "quality",
                 "description": "Missing docstring", "suggestion": "Add docstring"}
            ],
            "improvements":    [],
            "security_assessment": {
                "score":            90,
                "vulnerabilities":  [],
                "recommendations":  [],
            },
            "test_coverage_assessment": {
                "estimated_coverage": 88,
                "missing_tests":      [],
                "recommendations":    [],
            },
            "approved": True,
        }

        with patch("app.agents.code_reviewer.bedrock_service") as mock_bedrock:
            mock_bedrock.invoke_with_json_output = AsyncMock(return_value=mock_review)
            from app.agents.code_reviewer import CodeReviewerAgent
            agent = CodeReviewerAgent()
            result = await agent.execute(state)

        assert result["review_comments"]["overall_score"] == 85
        assert result["review_comments"]["approved"] is True
        assert result["current_step"] == "code_review"


# ─── LanguageProfiles ────────────────────────────────────────────────────────

class TestLanguageProfiles:
    def test_get_profile_exact_match(self):
        from app.agents.language_profiles import get_profile
        profile = get_profile("Python", "FastAPI")
        assert profile is not None
        assert profile.language == "Python"
        assert "FastAPI" in profile.primary_frameworks

    def test_get_profile_case_insensitive(self):
        from app.agents.language_profiles import get_profile
        assert get_profile("python", "fastapi") is not None
        assert get_profile("PYTHON", "FASTAPI") is not None

    def test_get_profile_language_fallback(self):
        from app.agents.language_profiles import get_profile
        # No "Python-Flask" profile exists; should fall back to first Python profile
        profile = get_profile("Python", "Flask")
        assert profile is not None
        assert profile.language == "Python"

    def test_get_profile_returns_none_for_unknown(self):
        from app.agents.language_profiles import get_profile
        assert get_profile("COBOL", "CICS") is None

    def test_all_profiles_have_required_fields(self):
        from app.agents.language_profiles import LANGUAGE_PROFILES
        required_fields = [
            "language", "primary_frameworks", "test_frameworks",
            "package_manager", "linters", "type_system", "async_pattern",
            "dependency_file", "orm_options", "di_pattern",
            "api_conventions", "code_style_guide", "agent_prompt_addendum",
        ]
        for key, profile in LANGUAGE_PROFILES.items():
            for field in required_fields:
                assert hasattr(profile, field), (
                    f"Profile '{key}' is missing field '{field}'"
                )
            assert profile.language,               f"Profile '{key}' has empty language"
            assert profile.primary_frameworks,     f"Profile '{key}' has empty frameworks"
            assert profile.test_frameworks,        f"Profile '{key}' has empty test frameworks"


# ─── BedrockService ──────────────────────────────────────────────────────────

class TestBedrockService:
    def test_parse_json_response_strips_fences(self):
        from app.services.bedrock import BedrockService
        svc = BedrockService()

        json_with_fence = '```json\n{"key": "value"}\n```'
        assert svc._parse_json_response(json_with_fence) == {"key": "value"}

        plain_json = '{"key": "value"}'
        assert svc._parse_json_response(plain_json) == {"key": "value"}

        json_with_plain_fence = '```\n{"key": "value"}\n```'
        assert svc._parse_json_response(json_with_plain_fence) == {"key": "value"}

    def test_parse_json_response_raises_on_invalid(self):
        from app.services.bedrock import BedrockService
        import json
        svc = BedrockService()
        with pytest.raises(json.JSONDecodeError):
            svc._parse_json_response("not valid json")
