import pytest
from unittest.mock import AsyncMock, patch
from app.agents.package_validation_agent import PackageValidationAgent


class TestPackageValidationAgent:
    """Test suite for PackageValidationAgent."""

    @pytest.fixture
    def agent(self):
        """Create a PackageValidationAgent instance for testing."""
        return PackageValidationAgent()

    @pytest.fixture
    def sample_state(self):
        """Sample state with code files for testing."""
        return {
            "project_id": "test-project-123",
            "run_id": "test-run-456", 
            "requirements": "Build a Node.js API",
            "code_files": [
                {
                    "path": "package.json",
                    "content": """{
  "name": "test-app",
  "version": "1.0.0",
  "dependencies": {
    "express": "^4.21.0",
    "typescript": "^5.6.2"
  },
  "devDependencies": {
    "eslint": "^8.57.1",
    "jest": "^29.7.0"
  }
}"""
                },
                {
                    "path": "tsconfig.json", 
                    "content": """{
  "compilerOptions": {
    "target": "ES2022",
    "module": "Node16"
  }
}"""
                },
                {
                    "path": "src/app.ts",
                    "content": "import express from 'express';"
                }
            ],
            "test_files": [],
            "devops_files": [
                {
                    "path": "Dockerfile",
                    "content": "FROM node:16-alpine"
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_agent_initialization(self, agent):
        """Test that agent initializes correctly."""
        assert agent.name == "PackageValidator"
        assert "validates generated packages" in agent.description.lower()
        assert hasattr(agent, 'bedrock')
        assert hasattr(agent, 'logger')

    @pytest.mark.asyncio
    async def test_execute_validates_config_files(self, agent, sample_state):
        """Test that execute method processes configuration files."""
        # Mock the LLM response for package.json validation
        mock_response = {
            "status": "issues_found",
            "issues": [
                {
                    "severity": "critical",
                    "package": "eslint", 
                    "issue": "ESLint 8.x is deprecated",
                    "fix": "Update to eslint ^9.0.0"
                }
            ],
            "critical_issues": ["eslint: ESLint 8.x is deprecated"],
            "updated_package_json": "{ updated content }",
            "migration_notes": []
        }

        with patch.object(agent, '_invoke_llm_json', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            
            result = await agent.execute(sample_state)
            
            # Verify state is updated correctly
            assert result["current_step"] == "package_validation"
            assert "validation_results" in result
            assert "critical_issues" in result
            assert "validation_passed" in result
            
            # Should have found critical issues
            assert len(result["critical_issues"]) > 0
            assert result["validation_passed"] is False
            
            # Verify validation results structure
            validation_results = result["validation_results"]
            assert len(validation_results) > 0
            
            # Check that package.json was processed
            package_result = next(
                (r for r in validation_results if "package.json" in r["file_path"]), 
                None
            )
            assert package_result is not None
            assert package_result["status"] == "issues_found"

    @pytest.mark.asyncio
    async def test_validate_package_json_deprecated_packages(self, agent):
        """Test package.json validation identifies deprecated packages."""
        deprecated_package_json = """{
  "name": "test-app",
  "dependencies": {
    "express": "^4.21.0"
  },
  "devDependencies": {
    "eslint": "^8.57.1",
    "ts-node-dev": "^2.0.0",
    "jest": "^29.7.0"
  }
}"""

        mock_response = {
            "status": "issues_found",
            "issues": [
                {
                    "severity": "critical", 
                    "package": "eslint",
                    "issue": "ESLint 8.x is deprecated, use 9.x",
                    "fix": "Update to eslint ^9.0.0"
                },
                {
                    "severity": "warning",
                    "package": "ts-node-dev", 
                    "issue": "ts-node-dev is deprecated",
                    "fix": "Use tsx or ts-node directly"
                }
            ],
            "critical_issues": ["eslint: ESLint 8.x deprecated"],
            "updated_package_json": "{ corrected version }",
            "migration_notes": ["ESLint 9 has breaking changes"]
        }

        with patch.object(agent, '_invoke_llm_json', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            
            result = await agent._validate_package_json("package.json", deprecated_package_json)
            
            assert result["status"] == "issues_found"
            assert len(result["issues"]) >= 2
            assert len(result["critical_issues"]) >= 1
            assert "updated_package_json" in result
            
            # Verify critical issues are identified
            critical_issues = result["critical_issues"]
            assert any("eslint" in issue.lower() for issue in critical_issues)

    @pytest.mark.asyncio 
    async def test_validate_package_json_current_packages(self, agent):
        """Test package.json validation passes for current packages."""
        current_package_json = """{
  "name": "test-app",
  "dependencies": {
    "express": "^4.21.0",
    "typescript": "^5.6.2"
  },
  "devDependencies": {
    "eslint": "^9.0.0",
    "jest": "^30.0.0",
    "@typescript-eslint/eslint-plugin": "^9.0.0"
  }
}"""

        mock_response = {
            "status": "valid",
            "issues": [],
            "critical_issues": [],
            "updated_package_json": current_package_json,
            "migration_notes": []
        }

        with patch.object(agent, '_invoke_llm_json', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            
            result = await agent._validate_package_json("package.json", current_package_json)
            
            assert result["status"] == "valid"
            assert len(result["issues"]) == 0
            assert len(result["critical_issues"]) == 0

    @pytest.mark.asyncio
    async def test_validate_tsconfig_outdated_settings(self, agent):
        """Test TypeScript config validation identifies outdated settings."""
        outdated_tsconfig = """{
  "compilerOptions": {
    "target": "ES2020",
    "module": "Node16",
    "moduleResolution": "Node16"
  }
}"""

        mock_response = {
            "status": "issues_found",
            "issues": [
                {
                    "severity": "warning",
                    "package": "typescript-config",
                    "issue": "module: Node16 is outdated",
                    "fix": "Update to Node20 or NodeNext"
                }
            ],
            "critical_issues": [],
            "updated_config": "{ corrected tsconfig }",
            "migration_notes": []
        }

        with patch.object(agent, '_invoke_llm_json', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            
            result = await agent._validate_tsconfig("tsconfig.json", outdated_tsconfig)
            
            assert result["status"] == "issues_found"
            assert len(result["issues"]) >= 1

    @pytest.mark.asyncio
    async def test_validate_dockerfile_outdated_base_image(self, agent):
        """Test Dockerfile validation identifies outdated base images."""
        outdated_dockerfile = "FROM node:16-alpine\nRUN npm install"

        mock_response = {
            "status": "issues_found", 
            "issues": [
                {
                    "severity": "warning",
                    "package": "node-base-image",
                    "issue": "Node.js 16 is EOL, use 20 LTS",
                    "fix": "Update to FROM node:20-alpine"
                }
            ],
            "critical_issues": [],
            "updated_dockerfile": "FROM node:20-alpine\\nRUN npm install",
            "migration_notes": []
        }

        with patch.object(agent, '_invoke_llm_json', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            
            result = await agent._validate_dockerfile("Dockerfile", outdated_dockerfile)
            
            assert result["status"] == "issues_found"
            assert len(result["issues"]) >= 1

    @pytest.mark.asyncio
    async def test_execute_handles_llm_errors_gracefully(self, agent, sample_state):
        """Test that agent handles LLM errors gracefully."""
        with patch.object(agent, '_invoke_llm_json', new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("LLM connection failed")
            
            result = await agent.execute(sample_state)
            
            # Should still return valid state structure
            assert "validation_results" in result
            assert "critical_issues" in result
            assert "validation_passed" in result
            assert "current_step" in result
            
            # Check that errors are recorded
            validation_results = result["validation_results"]
            assert len(validation_results) > 0
            
            # At least one result should have an error
            error_results = [r for r in validation_results if r.get("status") == "error"]
            assert len(error_results) > 0

    @pytest.mark.asyncio
    async def test_filters_config_files_correctly(self, agent):
        """Test that agent only processes relevant configuration files."""
        state = {
            "code_files": [
                {"path": "package.json", "content": "{}"},
                {"path": "src/app.ts", "content": "code"},
                {"path": "README.md", "content": "docs"}
            ],
            "test_files": [
                {"path": "jest.config.js", "content": "{}"},
                {"path": "tests/app.test.ts", "content": "test"}
            ],
            "devops_files": [
                {"path": "Dockerfile", "content": "FROM node:20"},
                {"path": "docker-compose.yml", "content": "version: 3"}
            ]
        }

        with patch.object(agent, '_validate_file', new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = {"status": "valid", "issues": [], "critical_issues": []}
            
            await agent.execute(state)
            
            # Should only call _validate_file for config files
            call_args = [call.kwargs["file_path"] for call in mock_validate.call_args_list]
            
            # Should include config files
            assert "package.json" in call_args
            assert "jest.config.js" in call_args  
            assert "Dockerfile" in call_args
            
            # Should NOT include source/test/doc files
            assert "src/app.ts" not in call_args
            assert "tests/app.test.ts" not in call_args
            assert "README.md" not in call_args