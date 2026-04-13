"""
Directive Service - Provides consistent coding standards and best practices
based on the deftai/directive framework for all AI agents in AgentForge.

This service ensures uniform code generation across all projects.
"""

import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
import yaml
import json
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class DirectiveLevel(Enum):
    """Hierarchy of directive precedence (highest to lowest)"""
    USER = "user"           # Personal preferences (highest precedence)  
    PROJECT = "project"     # Project-specific rules
    LANGUAGE = "language"   # Language standards
    TOOL = "tool"          # Tool guidelines  
    MAIN = "main"          # General AI behavior
    SPECIFICATION = "specification"  # Project requirements (lowest)


@dataclass
class DirectiveRule:
    """A single directive rule with precedence and notation"""
    content: str
    level: DirectiveLevel
    priority: str  # '!' = MUST, '~' = SHOULD, '≉' = SHOULD NOT, '⊗' = MUST NOT
    category: str  # e.g., 'coding', 'testing', 'architecture'
    

class DirectiveService:
    """
    Service for managing and applying directive-based coding standards.
    
    Implements the deftai/directive framework to ensure consistent,
    high-quality code generation across all projects and languages.
    """
    
    def __init__(self):
        self.rules_cache: Dict[str, List[DirectiveRule]] = {}
        self.standards: Dict[str, Dict[str, Any]] = {}
        self._load_base_standards()
    
    def _load_base_standards(self):
        """Load base coding standards from the directive framework"""
        
        # Core directive principles based on deftai/directive
        self.standards = {
            "general": {
                "principles": [
                    "! Correctness over convenience - optimize for long-term quality",
                    "! Standards over flexibility - consistent patterns across projects", 
                    "! Evolution over perfection - continuously improve through learning",
                    "! Clarity over cleverness - direct, explicit, maintainable code",
                    "! Test-Driven Development (TDD) as default approach",
                    "~ ≥85% test coverage (overall + per-module)",
                    "! Convention over configuration",
                    "! Safety and reversibility in all changes"
                ],
                "quality": [
                    "! Always run quality checks before commits",
                    "! Never claim checks passed without running them", 
                    "~ Use semantic versioning for releases",
                    "! Use Conventional Commits for all commits",
                    "~ Keep secrets in dedicated secrets directory",
                    "≉ Force-push without explicit permission",
                    "⊗ Skip tests or quality checks in production code"
                ],
                "file_structure": [
                    "~ Use hyphens in filenames, not underscores",
                    "! Keep docs in docs/ directory, not project root",
                    "! Organize code by domain/feature, not by type",
                    "~ Use consistent directory structure across projects"
                ]
            },
            
            "python": {
                "standards": [
                    "! Python ≥3.11 for all new projects",
                    "! Use ruff for linting and formatting (replaces black/flake8)",
                    "! Use mypy with --strict mode for type checking",
                    "! Use pytest for testing with pytest-asyncio for async code",
                    "! Achieve ≥85% test coverage with pytest-cov",
                    "~ Use pydantic for data validation and serialization",
                    "~ Use pathlib.Path instead of os.path",
                    "~ Use dataclasses or pydantic models for structured data",
                    "≉ Use bare except: clauses",
                    "⊗ Use eval() or exec() in production code"
                ],
                "testing": [
                    "! Write tests first (TDD)",
                    "! Use descriptive test names: test_should_do_something_when_condition", 
                    "! Use pytest fixtures for test setup",
                    "! Mock external dependencies in unit tests",
                    "~ Use parametrize for multiple test cases",
                    "~ Separate unit, integration, and end-to-end tests",
                    "≉ Test implementation details, test behavior"
                ],
                "async": [
                    "! Use asyncio for I/O-bound operations",
                    "! Use async/await syntax, not callbacks",
                    "~ Use aiohttp for HTTP clients", 
                    "~ Use asyncpg for PostgreSQL connections",
                    "! Properly handle async context managers",
                    "≉ Mix sync and async code unnecessarily"
                ]
            },
            
            "typescript": {
                "standards": [
                    "! TypeScript ≥5.0 with strict mode enabled",
                    "! Use ESLint with @typescript-eslint rules",
                    "! Use Prettier for code formatting",
                    "! Use Vitest for testing (replaces Jest)",
                    "! Achieve ≥85% test coverage",
                    "~ Use Zod for runtime type validation",
                    "~ Use interface over type for object shapes",
                    "~ Use const assertions for immutable data",
                    "≉ Use 'any' type except for gradual migration",
                    "⊗ Use 'eval' or 'Function' constructor"
                ],
                "react": [
                    "! Use React ≥18 with hooks",
                    "! Use TypeScript for all React components",
                    "! Use React Query/TanStack Query for server state",
                    "~ Use Zustand for client state management",
                    "~ Use React Hook Form for forms",
                    "~ Use Tailwind CSS for styling",
                    "≉ Use class components, prefer functions",
                    "≉ Mutate state directly, use immutable updates"
                ]
            },
            
            "go": {
                "standards": [
                    "! Go ≥1.21 for all new projects",
                    "! Follow effective Go guidelines",
                    "! Use gofmt and goimports for formatting",
                    "! Use golangci-lint for comprehensive linting",
                    "! Use testify for testing assertions",
                    "! Achieve ≥85% test coverage",
                    "~ Use context.Context for cancellation",
                    "~ Use structured logging (slog)",
                    "≉ Use panic() except for unrecoverable errors",
                    "⊗ Ignore errors without explicit handling"
                ]
            },
            
            "api_design": {
                "rest": [
                    "! Use RESTful conventions for HTTP APIs",
                    "! Use appropriate HTTP status codes",
                    "! Use JSON for request/response bodies",
                    "! Implement proper error responses with details",
                    "! Use OpenAPI/Swagger for API documentation",
                    "~ Use plural nouns for resource endpoints",
                    "~ Use HTTP verbs appropriately (GET, POST, PUT, DELETE)",
                    "~ Implement pagination for list endpoints",
                    "~ Use HTTP caching headers where appropriate"
                ],
                "security": [
                    "! Validate all inputs",
                    "! Use HTTPS in production",
                    "! Implement proper authentication and authorization",
                    "! Use secure headers (CORS, CSP, etc.)",
                    "! Rate limit all endpoints",
                    "≉ Log sensitive data",
                    "⊗ Trust client-provided data without validation"
                ]
            },
            
            "database": {
                "general": [
                    "! Use database migrations for schema changes",
                    "! Use database indexes for query optimization", 
                    "! Use connection pooling",
                    "! Use transactions for multi-step operations",
                    "~ Use database constraints for data integrity",
                    "~ Use foreign keys for referential integrity",
                    "≉ Use SELECT * in production queries",
                    "⊗ Store passwords in plain text"
                ],
                "sql": [
                    "! Use parameterized queries to prevent SQL injection",
                    "! Use appropriate data types for columns",
                    "~ Use meaningful table and column names",
                    "~ Use consistent naming conventions",
                    "≉ Use NOLOCK hints without understanding implications"
                ]
            },
            
            "docker": {
                "standards": [
                    "! Use multi-stage builds for production images",
                    "! Run containers as non-root user",
                    "! Use specific tags, not 'latest' in production",
                    "! Use .dockerignore to exclude unnecessary files",
                    "~ Use Alpine Linux for smaller images where possible",
                    "~ Use health checks for services",
                    "~ Minimize layers and use layer caching",
                    "≉ Install unnecessary packages in production images"
                ]
            }
        }
        
        logger.info("Loaded directive-based coding standards")
    
    def get_standards_for_language(self, language: str) -> Dict[str, Any]:
        """Get coding standards for a specific language"""
        language_key = language.lower().replace(" ", "").replace("#", "sharp")
        
        # Always include general standards
        standards = {
            "general": self.standards.get("general", {}),
            "api_design": self.standards.get("api_design", {}),
            "database": self.standards.get("database", {}),
            "docker": self.standards.get("docker", {})
        }
        
        # Add language-specific standards
        if language_key in self.standards:
            standards[language_key] = self.standards[language_key]
        
        return standards
    
    def get_standards_for_framework(self, framework: str) -> Dict[str, Any]:
        """Get standards for a specific framework"""
        framework_standards = {}
        framework_key = framework.lower().replace(".", "").replace(" ", "")
        
        # Framework-specific mappings
        framework_mapping = {
            "fastapi": ["python", "api_design"],
            "django": ["python", "api_design"], 
            "flask": ["python", "api_design"],
            "express": ["typescript", "api_design"],
            "nestjs": ["typescript", "api_design"],
            "nextjs": ["typescript", "react"],
            "react": ["typescript", "react"],
            "gin": ["go", "api_design"],
            "fiber": ["go", "api_design"],
            "echo": ["go", "api_design"]
        }
        
        relevant_standards = framework_mapping.get(framework_key, [])
        for standard_key in relevant_standards:
            if standard_key in self.standards:
                framework_standards[standard_key] = self.standards[standard_key]
        
        return framework_standards
    
    def generate_coding_directive(
        self, 
        language: str, 
        framework: Optional[str] = None,
        project_type: str = "api"
    ) -> str:
        """
        Generate a comprehensive coding directive for AI agents.
        
        This directive ensures consistent, high-quality code generation
        following the deftai/directive principles.
        """
        
        directive_parts = []
        
        # Header
        directive_parts.append(f"""
# Coding Directive for {language}{"/" + framework if framework else ""} Project

You are an expert software engineer following the deftai/directive framework 
for consistent, high-quality code generation. Apply these standards strictly.

## Notation Legend
- **!** = MUST (required, mandatory)
- **~** = SHOULD (recommended, strong preference)  
- **≉** = SHOULD NOT (discouraged, avoid unless justified)
- **⊗** = MUST NOT (forbidden, never do this)

""")
        
        # General standards
        if "general" in self.standards:
            directive_parts.append("## General Principles\n")
            for category, rules in self.standards["general"].items():
                directive_parts.append(f"### {category.title()}\n")
                for rule in rules:
                    directive_parts.append(f"- {rule}")
                directive_parts.append("")
        
        # Language-specific standards
        language_standards = self.get_standards_for_language(language)
        language_key = language.lower().replace(" ", "").replace("#", "sharp")
        
        if language_key in language_standards:
            directive_parts.append(f"## {language} Standards\n")
            for category, rules in language_standards[language_key].items():
                directive_parts.append(f"### {category.title()}\n")
                for rule in rules:
                    directive_parts.append(f"- {rule}")
                directive_parts.append("")
        
        # Framework-specific standards
        if framework:
            framework_standards = self.get_standards_for_framework(framework)
            if framework_standards:
                directive_parts.append(f"## {framework} Framework Standards\n")
                for standard_type, categories in framework_standards.items():
                    if standard_type != language_key:  # Avoid duplication
                        directive_parts.append(f"### {standard_type.title()}\n")
                        if isinstance(categories, dict):
                            for category, rules in categories.items():
                                directive_parts.append(f"#### {category.title()}\n") 
                                for rule in rules:
                                    directive_parts.append(f"- {rule}")
                                directive_parts.append("")
        
        # API Design standards (always included for APIs)
        if project_type == "api" and "api_design" in self.standards:
            directive_parts.append("## API Design Standards\n")
            for category, rules in self.standards["api_design"].items():
                directive_parts.append(f"### {category.title()}\n")
                for rule in rules:
                    directive_parts.append(f"- {rule}")
                directive_parts.append("")
        
        # Database standards
        if "database" in self.standards:
            directive_parts.append("## Database Standards\n")
            for category, rules in self.standards["database"].items():
                directive_parts.append(f"### {category.title()}\n")
                for rule in rules:
                    directive_parts.append(f"- {rule}")
                directive_parts.append("")
        
        # Docker standards
        if "docker" in self.standards:
            directive_parts.append("## Docker Standards\n")
            for category, rules in self.standards["docker"].items():
                directive_parts.append(f"### {category.title()}\n")
                for rule in rules:
                    directive_parts.append(f"- {rule}")
                directive_parts.append("")
        
        # Quality enforcement
        directive_parts.append("""
## Quality Enforcement

! BEFORE generating ANY code:
1. Read and internalize ALL standards above
2. Plan the implementation following TDD principles
3. Ensure all quality requirements are met

! DURING code generation:
1. Write tests first (Red-Green-Refactor cycle)
2. Follow language-specific conventions strictly
3. Include proper error handling and logging
4. Add comprehensive documentation

! AFTER code generation:
1. Verify ≥85% test coverage
2. Ensure all quality checks would pass
3. Review for security vulnerabilities
4. Confirm standards compliance

## Remember
- Quality over speed - take time to do it right
- Consistency across all files and components  
- Self-documenting code with clear naming
- Fail fast with meaningful error messages
- No shortcuts on testing or security

Follow these directives without exception. Your reputation as a software engineer depends on the quality and consistency of the code you generate.
""")
        
        return "\n".join(directive_parts)
    
    def get_task_automation_standards(self) -> str:
        """Get standards for task automation (Taskfile, build scripts, etc.)"""
        return """
# Task Automation Standards

## Taskfile.yml Structure
! Use Taskfile.yml as the universal task runner
! Include these standard tasks:
- `dev`: Start development environment
- `test`: Run tests in watch mode
- `test:coverage`: Run tests with coverage report
- `check`: Pre-commit checks (lint, format, type-check, test)
- `build`: Build the application
- `clean`: Clean build artifacts

## Task Naming
~ Use colon notation for task namespacing (test:coverage, docker:build)
~ Use descriptive task names
~ Include task descriptions using `desc:` field

## Cross-Platform Support
! Ensure tasks work on Linux, macOS, and Windows
! Use Taskfile's built-in variables for path handling
! Test commands on multiple platforms

## Dependencies
! Use `deps:` for task dependencies
! Use `preconditions:` for runtime checks
! Use `sources:` and `generates:` for incremental builds
"""

    def get_verification_standards(self) -> str:
        """Get standards for verification and quality assurance"""
        return """
# Verification Standards (4-Tier Verification Ladder)

## Tier 1: Static Analysis
! Code compiles/parses without errors
! Linting passes with zero warnings
! Type checking passes (mypy --strict, tsc --noEmit)
! Formatting is consistent

## Tier 2: Unit Testing  
! All unit tests pass
! ≥85% code coverage achieved
! Tests are fast (< 1s per test typically)
! Tests are isolated and deterministic

## Tier 3: Integration Testing
! Integration tests pass
! External dependencies are tested
! API contracts are validated
! Database migrations work

## Tier 4: End-to-End Testing
! Critical user journeys work
! Performance requirements met
! Security requirements satisfied
! Deployment works in staging

## Continuous Verification
! Set up pre-commit hooks
! Run verification pipeline on every PR
! Block merges if verification fails
! Monitor production metrics
"""


# Global instance
directive_service = DirectiveService()