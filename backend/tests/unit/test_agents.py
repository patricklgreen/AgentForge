"""
Unit tests for all agent classes.
Each test uses mocked LLM/service calls — no real AWS calls.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def base_state():
    return {
        "project_id": "test-project-id",
        "run_id": "test-run-id",
        "requirements": (
            "Build a RESTful API for an e-commerce platform with user auth, "
            "product catalog, shopping cart, and order processing."
        ),
        "target_language": "Python",
        "target_framework": "FastAPI",
        "code_files": [],
        "test_files": [],
        "devops_files": [],
        "current_step": "starting",
        "validation_results": [],
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
                {"id": "FR-001", "title": "Auth", "description": "JWT auth"},
            ],
            "tech_stack": {"language": "Python", "framework": "FastAPI"},
        }

        from app.agents.requirements_analyst import RequirementsAnalystAgent
        agent = RequirementsAnalystAgent()
        
        # Mock the _invoke_llm_json method (new architecture)
        with patch.object(agent, '_invoke_llm_json', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_spec
            
            state = {**base_state, "specification": None, "target_framework": "FastAPI"}
            result = await agent.execute(state)

        assert result["specification"] is not None
        assert result["specification"]["project_name"] == "ecommerce-api"
        assert result["current_step"] == "requirements_analysis"


# ─── CodeGeneratorAgent ──────────────────────────────────────────────────────

class TestCodeGeneratorAgent:
    @pytest.mark.asyncio
    async def test_execute_generates_code_files(self, base_state):
        from app.agents.code_generator import CodeGeneratorAgent
        agent = CodeGeneratorAgent()
        
        mock_response = Mock()
        mock_response.content = "# Generated Python code\nprint('Hello, World!')"
        
        with patch.object(agent, '_invoke_llm', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            
            # Add some files to generate
            state = {
                **base_state,
                "files_to_generate": [
                    {"path": "src/main.py", "description": "Main application file"}
                ]
            }
            
            result = await agent.execute(state)

        assert "code_files" in result
        assert len(result["code_files"]) > 0
        assert result["current_step"] == "code_generation"


# ─── TestWriterAgent ─────────────────────────────────────────────────────────

class TestTestWriterAgent:
    @pytest.mark.asyncio
    async def test_execute_generates_test_files(self, base_state):
        from app.agents.test_writer import TestWriterAgent
        agent = TestWriterAgent()
        
        mock_response = Mock()
        mock_response.content = "# Generated test code\ndef test_example(): pass"
        
        with patch.object(agent, '_invoke_llm', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            
            # Add some code files to test
            state = {
                **base_state,
                "code_files": [
                    {"path": "src/main.py", "content": "print('Hello')"}
                ]
            }
            
            result = await agent.execute(state)

        assert "test_files" in result
        assert result["current_step"] == "test_writing"


# ─── ValidationAgent ─────────────────────────────────────────────────────────

class TestValidationAgent:
    @pytest.mark.asyncio
    async def test_execute_validates_code(self, base_state):
        from app.agents.validation_agent import ValidationAgent
        agent = ValidationAgent()
        
        mock_response = Mock()
        mock_response.content = '{"validation_passed": true, "issues": []}'
        
        with patch.object(agent, '_invoke_llm', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            
            state = {
                **base_state,
                "code_files": [
                    {"path": "src/main.py", "content": "print('Hello')"}
                ]
            }
            
            result = await agent.execute(state)

        assert "validation_passed" in result
        assert result["current_step"] == "code_validation"


# ─── DevOpsAgent ─────────────────────────────────────────────────────────────

class TestDevOpsAgent:
    @pytest.mark.asyncio
    async def test_execute_generates_devops_files(self, base_state):
        from app.agents.devops_agent import DevOpsAgent
        agent = DevOpsAgent()
        
        mock_response = Mock()
        mock_response.content = "# Generated Dockerfile\nFROM python:3.11"
        
        with patch.object(agent, '_invoke_llm', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            
            state = {**base_state}
            result = await agent.execute(state)

        assert "devops_files" in result
        assert result["current_step"] == "devops_setup"


# ─── DocumentationAgent ─────────────────────────────────────────────────────

class TestDocumentationAgent:
    @pytest.mark.asyncio
    async def test_execute_generates_documentation(self, base_state):
        from app.agents.documentation_agent import DocumentationAgent
        agent = DocumentationAgent()
        
        mock_response = Mock()
        mock_response.content = "# Project Documentation\nThis is a great project."
        
        with patch.object(agent, '_invoke_llm', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            
            state = {**base_state}
            result = await agent.execute(state)

        assert "documentation" in result
        assert result["current_step"] == "documentation"