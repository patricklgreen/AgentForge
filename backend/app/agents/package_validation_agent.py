import json
from datetime import datetime
from typing import Any, Dict, List

from app.agents.base import BaseAgent


_SYSTEM_PROMPT = """You are a Senior DevOps and Package Management Expert who validates generated code for production readiness.

Your responsibilities:
1. **Validate Package Versions**: Ensure all dependencies use current, non-deprecated versions
2. **Check Compatibility**: Verify package combinations work together without conflicts  
3. **Security Review**: Identify packages with known vulnerabilities or maintenance issues
4. **Best Practices**: Ensure modern configuration patterns and standards
5. **Runtime Verification**: Validate that the generated code will actually install and run

Current standards (April 2026):
- Node.js: 20.x LTS, 22.x Current
- TypeScript: 5.6+
- ESLint: 9.x (ESLint 8.x is deprecated)
- Jest: 30.x
- React: 18.x
- Express: 4.21+
- Prisma: 5.20+

For each file you review:
- Check package versions against current stable releases
- Identify deprecated packages and suggest modern alternatives  
- Verify configuration compatibility
- Test critical path dependencies
- Flag security vulnerabilities

Output a detailed validation report with:
- ✅ Valid packages and configurations
- ⚠️  Issues found with severity level
- 🔧 Specific fix recommendations
- 📋 Updated package.json with current versions

Be thorough but practical - focus on issues that will cause build/runtime failures."""


class PackageValidationAgent(BaseAgent):
    """
    Validates generated packages for current versions, security, and compatibility.
    Ensures generated code uses up-to-date dependencies that will actually work.
    """

    def __init__(self):
        super().__init__(
            name="PackageValidator",
            description="Validates generated packages for current versions, security, and compatibility"
        )

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Validate all generated files for package currency and compatibility."""
        code_files = state.get("code_files", [])
        test_files = state.get("test_files", [])
        devops_files = state.get("devops_files", [])
        
        all_files = code_files + test_files + devops_files
        validation_results = []
        critical_issues = []
        
        # Focus on key configuration files
        config_files = [
            f for f in all_files 
            if any(pattern in f["path"].lower() for pattern in [
                "package.json", "tsconfig.json", "dockerfile", "docker-compose", 
                "eslint", "jest.config", "vite.config", "webpack.config"
            ])
        ]
        
        self._log_step(f"Validating {len(config_files)} configuration files for current packages...")
        
        for config_file in config_files:
            file_path = config_file["path"]
            file_content = config_file.get("content", "")
            
            self._log_step(f"Validating {file_path}...")
            
            try:
                validation_result = await self._validate_file(
                    file_path=file_path,
                    content=file_content,
                    all_files=all_files
                )
                
                validation_results.append(validation_result)
                
                # Collect critical issues
                if validation_result.get("critical_issues"):
                    critical_issues.extend(validation_result["critical_issues"])
                    
            except Exception as e:
                self.logger.error(f"Validation failed for {file_path}: {e}")
                validation_results.append({
                    "file_path": file_path,
                    "status": "error",
                    "error": str(e)
                })

        self._log_step(f"Validation complete - {len(critical_issues)} critical issues found")
        
        return {
            **state,
            "validation_results": validation_results,
            "critical_issues": critical_issues,
            "validation_passed": len(critical_issues) == 0,
            "current_step": "package_validation"
        }

    async def _validate_file(
        self, 
        file_path: str, 
        content: str, 
        all_files: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Validate a specific configuration file."""
        
        if "package.json" in file_path:
            return await self._validate_package_json(file_path, content)
        elif "tsconfig.json" in file_path:
            return await self._validate_tsconfig(file_path, content)
        elif "dockerfile" in file_path.lower():
            return await self._validate_dockerfile(file_path, content)
        else:
            return await self._validate_generic_config(file_path, content)

    async def _validate_package_json(self, file_path: str, content: str) -> Dict[str, Any]:
        """Validate package.json for current versions and compatibility."""
        
        user_message = f"""
Validate this package.json for production readiness in April 2026:

```json
{content}
```

**Critical validation points:**
1. **Package Currency**: Are all packages using current, supported versions?
2. **Deprecated Packages**: Identify any deprecated packages that should be replaced
3. **Security**: Check for packages with known vulnerabilities  
4. **Compatibility**: Verify package combinations work together
5. **Missing Essentials**: Any critical packages missing for the tech stack?
6. **Libraries should not conflict with each other
7. **Libraries should not contain any security vulnerabilities

**Specific concerns to check:**
- ESLint 8.x is deprecated (use 9.x)
- TypeScript compatibility with chosen Node.js version
- Jest vs Vitest for testing
- Express security middleware completeness
- Database client version compatibility
- AWS SDK v3 usage (not v2)

Provide:
1. **Issues Found**: List all problems with severity (🔴 Critical, ⚠️ Warning, ℹ️ Info)
2. **Updated package.json**: Complete fixed version with current packages
3. **Migration Notes**: Any breaking changes to watch for

Output as JSON with structure:
{{
  "status": "issues_found" | "valid",
  "issues": [{{"severity": "critical|warning|info", "package": "", "issue": "", "fix": ""}}],
  "critical_issues": ["list of critical problems"],
  "updated_package_json": "complete corrected JSON string",
  "migration_notes": ["any breaking changes to watch for"]
}}
"""

        try:
            response = await self._invoke_llm_json(
                system_prompt=_SYSTEM_PROMPT,
                user_message=user_message,
                include_directive=True,
                state={
                    "specification": {"target_language": "javascript", "target_framework": "node"},
                    "requirements": "Validate package.json with directive standards"
                }
            )
            
            return {
                "file_path": file_path,
                **response
            }
            
        except Exception as e:
            return {
                "file_path": file_path,
                "status": "error",
                "error": f"Failed to validate package.json: {e}"
            }

    async def _validate_tsconfig(self, file_path: str, content: str) -> Dict[str, Any]:
        """Validate TypeScript configuration."""
        
        user_message = f"""
Validate this tsconfig.json for current TypeScript best practices (April 2026):

```json
{content}
```

Check for:
1. **Target/Module versions**: Are they current? 
2. **Compiler options**: Missing important flags?
3. **Path mapping**: Proper setup?
4. **Strict settings**: Production-ready strictness?
5. **Node.js compatibility**: Matches package.json engines?

Provide JSON response with issues and corrected config.
"""

        try:
            response = await self._invoke_llm_json(
                system_prompt=_SYSTEM_PROMPT,
                user_message=user_message,
                include_directive=True,
                state={
                    "specification": {"target_language": "typescript", "target_framework": "typescript"},
                    "requirements": "Validate TypeScript config with directive standards"
                }
            )
            
            return {
                "file_path": file_path,
                **response
            }
            
        except Exception as e:
            return {
                "file_path": file_path,
                "status": "error", 
                "error": f"Failed to validate tsconfig.json: {e}"
            }

    async def _validate_dockerfile(self, file_path: str, content: str) -> Dict[str, Any]:
        """Validate Dockerfile for security and best practices."""
        
        user_message = f"""
Validate this Dockerfile for production readiness (April 2026):

```dockerfile
{content}
```

Check for:
1. **Base image currency**: Using latest LTS versions?
2. **Security practices**: Non-root user, layer optimization?
3. **Build efficiency**: Multi-stage builds, caching?
4. **Runtime config**: Proper ports, health checks?

Provide JSON response with issues and corrections.
"""

        try:
            response = await self._invoke_llm_json(
                system_prompt=_SYSTEM_PROMPT,
                user_message=user_message,
                include_directive=True,
                state={
                    "specification": {"target_language": "docker", "target_framework": "docker"},
                    "requirements": "Validate Dockerfile with directive security standards"
                }
            )
            
            return {
                "file_path": file_path,
                **response
            }
            
        except Exception as e:
            return {
                "file_path": file_path,
                "status": "error",
                "error": f"Failed to validate Dockerfile: {e}"
            }

    async def _validate_generic_config(self, file_path: str, content: str) -> Dict[str, Any]:
        """Validate other configuration files."""
        
        return {
            "file_path": file_path,
            "status": "skipped",
            "note": "Generic config validation not implemented yet"
        }

    def _log_step(self, message: str) -> None:
        """Log a validation step."""
        self.logger.info(f"📋 PackageValidation: {message}")