"""
Generate directive configuration files for projects to ensure
consistent standards and best practices.
"""

import logging
from typing import Dict, Any, Optional
from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are an expert in software engineering best practices and 
the deftai/directive framework. You generate configuration files that enforce
consistent, high-quality coding standards across projects.

Follow the directive notation:
- ! = MUST (required, mandatory)
- ~ = SHOULD (recommended, strong preference)
- ≉ = SHOULD NOT (discouraged, avoid unless justified)  
- ⊗ = MUST NOT (forbidden, never do this)

Generate production-ready configuration files with comprehensive coverage."""


class DirectiveConfigGenerator(BaseAgent):
    """Generates directive-based configuration files for projects."""
    
    def __init__(self):
        super().__init__(
            name="DirectiveConfigGenerator",
            description="Generates directive-based configuration files for consistent project standards"
        )
    
    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute method required by BaseAgent - not used directly"""
        return state
    
    async def generate_project_directive(self, specification: Dict[str, Any]) -> str:
        """Generate a PROJECT.md directive file for the project"""
        
        project_name = specification.get("project_name", "Application")
        target_language = specification.get("target_language", "Python")
        target_framework = specification.get("target_framework", "")
        project_type = self._determine_project_type(specification)
        
        user_message = f"""
Generate a PROJECT.md directive file for this project:

**Project:** {project_name}
**Language:** {target_language}
**Framework:** {target_framework}
**Type:** {project_type}

**Requirements:**
{specification.get("project_description", "")}

**Tech Stack:**
{specification.get("tech_stack", {})}

The PROJECT.md should include:
1. Project-specific overrides for the base directive standards
2. Custom rules specific to this project's domain and requirements
3. Team conventions and patterns
4. Deployment and environment specifics
5. Documentation standards for this project
6. Quality gates and acceptance criteria

Use directive notation (!, ~, ≉, ⊗) throughout.
Output ONLY the PROJECT.md content.
"""
        
        content = await self._invoke_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_message=user_message,
            include_directive=True,
            state={
                "specification": specification,
                "requirements": specification.get("project_description", "")
            }
        )
        
        return content
    
    async def generate_taskfile_yml(self, specification: Dict[str, Any]) -> str:
        """Generate a comprehensive Taskfile.yml following directive standards"""
        
        target_language = specification.get("target_language", "Python")
        target_framework = specification.get("target_framework", "")
        tech_stack = specification.get("tech_stack", {})
        
        user_message = f"""
Generate a comprehensive Taskfile.yml for this project:

**Language:** {target_language}
**Framework:** {target_framework}  
**Tech Stack:** {tech_stack}
**Database:** {tech_stack.get("database", "")}
**Testing:** {tech_stack.get("testing", "")}

Follow directive task automation standards:
! Include these standard tasks with proper desc: fields:
- dev: Start development environment
- test: Run tests in watch mode  
- test:coverage: Run tests with coverage report ≥85%
- check: Pre-commit checks (lint, format, type-check, test)
- build: Build the application
- clean: Clean build artifacts
- setup: Install dependencies and setup project
- format: Format code consistently
- lint: Run comprehensive linting
- docker:build: Build Docker images
- docker:up: Start Docker services
- docker:down: Stop Docker services

~ Add language/framework specific tasks as needed
~ Use proper task dependencies with deps:
~ Use preconditions: for runtime checks  
~ Use sources: and generates: for incremental builds
! Ensure cross-platform compatibility (Windows/Mac/Linux)
~ Include helpful task descriptions

Output ONLY the Taskfile.yml content.
"""
        
        content = await self._invoke_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_message=user_message,
            include_directive=True,
            state={
                "specification": specification,
                "requirements": specification.get("project_description", "")
            }
        )
        
        return content
    
    async def generate_agents_md(self, specification: Dict[str, Any]) -> str:
        """Generate AGENTS.md file that references the directive framework"""
        
        project_name = specification.get("project_name", "Application")
        target_language = specification.get("target_language", "Python")
        
        content = f"""# AI Agent Instructions for {project_name}

## Directive Framework Integration

This project follows the [deftai/directive](https://github.com/deftai/directive) framework for consistent, high-quality code generation.

### Quick Start for AI Agents

**! BEFORE starting any code generation:**
1. Read and internalize the directive standards for {target_language}
2. Review the project-specific rules in PROJECT.md  
3. Understand the task automation system in Taskfile.yml
4. Follow Test-Driven Development (TDD) principles

### Rule Hierarchy (highest to lowest precedence)
1. **PROJECT.md** - Project-specific overrides
2. **Language Standards** - {target_language} coding standards  
3. **Framework Standards** - Best practices and patterns
4. **General Standards** - Universal software engineering principles

### Quality Requirements
! Achieve ≥85% test coverage (overall + per-module)
! Use consistent naming conventions and code organization
! Follow security best practices (input validation, no secrets in code)
! Include comprehensive error handling and logging  
! Write self-documenting code with clear naming
~ Use static analysis tools (linters, type checkers)
~ Follow conventional commits for version control

### Task Automation
! Use Taskfile.yml for all automation tasks:
```bash
task --list          # See available tasks
task check           # Run all quality checks  
task test:coverage   # Verify test coverage
task dev             # Start development environment
```

### Code Generation Principles
! **Correctness over convenience** - optimize for long-term quality
! **Standards over flexibility** - consistent patterns across files
! **Clarity over cleverness** - direct, explicit, maintainable code
! **Evolution over perfection** - continuously improve through learning

## Project Context

**Language:** {target_language}
**Framework:** {specification.get("target_framework", "N/A")}
**Project Type:** {self._determine_project_type(specification)}

## Getting Started

When working on this project:
1. Run `task setup` to install dependencies
2. Run `task check` to verify everything works
3. Run `task dev` to start development environment  
4. Follow TDD: write tests first, then implementation
5. Run `task check` before committing any changes

## Standards Compliance

All code generated for this project must:
- Pass linting and formatting checks
- Achieve required test coverage thresholds
- Follow the established architectural patterns
- Include proper documentation and comments
- Handle errors gracefully with meaningful messages
- Be production-ready without modification

Remember: Your reputation as a software engineer depends on the quality and consistency of the code you generate. No shortcuts on testing, security, or code quality.
"""
        
        return content
    
    def _determine_project_type(self, specification: Dict[str, Any]) -> str:
        """Determine the project type from specification"""
        requirements = specification.get("project_description", "").lower()
        
        if any(term in requirements for term in ["api", "rest", "endpoint", "microservice"]):
            return "API/Microservice"
        elif any(term in requirements for term in ["web", "frontend", "react", "ui", "website"]):
            return "Web Application"  
        elif any(term in requirements for term in ["mobile", "ios", "android", "flutter"]):
            return "Mobile Application"
        elif any(term in requirements for term in ["cli", "command", "tool", "utility"]):
            return "CLI Tool"
        elif any(term in requirements for term in ["library", "package", "module", "sdk"]):
            return "Library/Package"
        else:
            return "Application"


# Global instance  
directive_config_generator = DirectiveConfigGenerator()