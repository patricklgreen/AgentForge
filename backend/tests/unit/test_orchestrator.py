import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from app.agents.orchestrator import AgentOrchestrator


class TestAgentOrchestrator:
    """Test suite for AgentOrchestrator workflow."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance for testing.""" 
        with patch('app.agents.orchestrator.AsyncPostgresSaver'):
            return AgentOrchestrator()

    @pytest.fixture
    def sample_state(self):
        """Sample project state for testing."""
        return {
            "project_id": "test-project-123",
            "run_id": "test-run-456",
            "requirements": "Build a Node.js REST API with authentication",
            "current_step": "requirements_analysis",
            "code_files": [],
            "test_files": [],
            "devops_files": [],
            "validation_passed": True
        }

    @pytest.mark.asyncio
    async def test_orchestrator_initialization(self, orchestrator):
        """Test that orchestrator initializes all agents correctly."""
        assert hasattr(orchestrator, 'requirements_analyst')
        assert hasattr(orchestrator, 'code_generator')
        assert hasattr(orchestrator, 'validation_agent')
        assert hasattr(orchestrator, 'package_validator')  # New agent
        assert hasattr(orchestrator, 'test_writer')
        assert hasattr(orchestrator, 'code_reviewer')
        assert hasattr(orchestrator, 'devops_agent')
        assert hasattr(orchestrator, 'documentation_agent')
        
        # Check that graph exists
        assert hasattr(orchestrator, 'graph')

    @pytest.mark.asyncio 
    async def test_package_validation_node_execution(self, orchestrator, sample_state):
        """Test that package validation node executes correctly."""
        # Mock the package validator
        mock_validation_result = {
            **sample_state,
            "validation_results": [
                {
                    "file_path": "package.json",
                    "status": "issues_found", 
                    "issues": [
                        {
                            "severity": "warning",
                            "package": "eslint",
                            "issue": "ESLint 8.x is deprecated",
                            "fix": "Update to eslint ^9.0.0"
                        }
                    ],
                    "critical_issues": []
                }
            ],
            "critical_issues": [],
            "validation_passed": True,
            "current_step": "package_validation"
        }
        
        orchestrator.package_validator.execute = AsyncMock(return_value=mock_validation_result)
        orchestrator._notify = AsyncMock()
        
        # Execute the package validation node
        result = await orchestrator._validate_packages_node(sample_state)
        
        # Verify execution
        orchestrator.package_validator.execute.assert_called_once_with(sample_state)
        orchestrator._notify.assert_called()
        
        # Check result structure  
        assert result["current_step"] == "package_validation"
        assert "validation_results" in result
        assert "critical_issues" in result
        assert "validation_passed" in result

    @pytest.mark.asyncio
    async def test_package_validation_critical_issues_handling(self, orchestrator, sample_state):
        """Test handling when package validation finds critical issues."""
        # Mock critical issues found
        mock_validation_result = {
            **sample_state,
            "validation_results": [
                {
                    "file_path": "package.json",
                    "status": "issues_found",
                    "issues": [
                        {
                            "severity": "critical",
                            "package": "lodash",
                            "issue": "Security vulnerability",
                            "fix": "Update to lodash ^4.17.21"
                        }
                    ],
                    "critical_issues": ["lodash: Security vulnerability"]
                }
            ],
            "critical_issues": ["lodash: Security vulnerability"],
            "validation_passed": False,
            "current_step": "package_validation"
        }
        
        orchestrator.package_validator.execute = AsyncMock(return_value=mock_validation_result)
        orchestrator._notify = AsyncMock()
        
        result = await orchestrator._validate_packages_node(sample_state)
        
        # Should still continue workflow but log critical issues
        assert result["validation_passed"] is False
        assert len(result["critical_issues"]) > 0
        
        # Verify notification of critical issues
        notify_calls = orchestrator._notify.call_args_list
        assert len(notify_calls) >= 1