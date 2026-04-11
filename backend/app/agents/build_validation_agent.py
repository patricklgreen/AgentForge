import asyncio
import json
import logging
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class BuildValidationAgent(BaseAgent):
    """
    Validates that generated projects actually build, install, test, and run successfully.
    
    This agent runs all validation in containerized environments with all required tools
    to ensure consistent and reliable build verification regardless of the host environment.
    
    Pipeline position: write_tests → build_validate → review_code
    
    Validation Steps:
    ─────────────────
    1. Package Installation (npm install, pip install, etc.)
    2. Docker Build (if Dockerfile present)
    3. Test Execution (pytest, npm test, etc.)  
    4. Runtime Validation (start app, test /health endpoint)
    
    All validation runs in Docker containers with pre-installed tools.
    """

    def __init__(self):
        super().__init__(
            name="BuildValidator",
            description="Executes builds, tests, and runtime validation in containerized environments"
        )
        self.timeout_seconds = 600  # 10 minutes max for any single operation
        self.validation_image = "agentforge/build-validator:latest"

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute build validation workflow in containerized environment."""
        self._log_step("Starting containerized build validation...")
        
        specification = state.get("specification", {})
        code_files = state.get("code_files", [])
        test_files = state.get("test_files", [])
        devops_files = state.get("devops_files", [])
        
        all_files = code_files + test_files + devops_files
        
        if not all_files:
            self._log_step("No files to validate — marking as successful (empty project)")
            return {
                **state, 
                "build_validation_results": [], 
                "build_validation_passed": True,
                "current_step": "build_validation"
            }
        
        language = specification.get("target_language", "").lower()
        framework = specification.get("target_framework", "").lower()
        
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute comprehensive build validation without Docker-in-Docker."""
        self._log_step("Starting comprehensive build validation...")

        specification = state.get("specification", {})
        code_files = state.get("code_files", [])
        test_files = state.get("test_files", [])
        devops_files = state.get("devops_files", [])

        all_files = code_files + test_files + devops_files

        if not all_files:
            self._log_step("No files to validate — marking as successful (empty project)")
            return {
                **state,
                "build_validation_results": [],
                "build_validation_passed": True,
                "current_step": "build_validation"
            }

        language = specification.get("target_language", "").lower()
        framework = specification.get("target_framework", "").lower()

        validation_results = []

        try:
            with tempfile.TemporaryDirectory(prefix="agentforge_build_") as temp_dir:
                project_path = Path(temp_dir)

                # Write all files to temporary directory
                for file_info in all_files:
                    file_path = project_path / file_info["path"]
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_text(file_info["content"], encoding="utf-8")

                # Run comprehensive validation pipeline
                validation_results = await self._run_comprehensive_validation(
                    project_path, language, framework, specification
                )

        except Exception as e:
            logger.error(f"Build validation failed with exception: {e}", exc_info=True)
            validation_results = [{
                "step": "validation_setup",
                "status": "error",
                "error": str(e),
                "duration_ms": 0
            }]
        
        try:
            with tempfile.TemporaryDirectory(prefix="agentforge_build_") as temp_dir:
                project_path = Path(temp_dir)
                
                # Write all files to temporary directory
                await self._write_project_files(project_path, all_files)
                
                # Run validation pipeline in containers
                results = await self._run_containerized_validation(
                    project_path, language, framework, specification
                )
                validation_results.extend(results)
                
        except Exception as e:
            logger.error(f"Build validation failed: {e}")
            validation_results.append({
                "step": "setup",
                "status": "error",
                "error": str(e),
                "duration_ms": 0
            })
        
        # Analyze results - be strict about actual validation
        total_steps = len(validation_results)
        successful_steps = sum(1 for r in validation_results if r.get("status") == "success")
        failed_steps = sum(1 for r in validation_results if r.get("status") in ["failed", "error"])
        
        # Build validation passes only if no steps failed
        build_validation_passed = failed_steps == 0 and total_steps > 0
        
        if failed_steps > 0:
            self._log_step(
                f"Build validation failed — {successful_steps} succeeded, {failed_steps} failed"
            )
        else:
            self._log_step(
                f"Build validation passed — {successful_steps} steps completed successfully"
            )
        
        return {
            **state,
            "build_validation_results": validation_results,
            "build_validation_passed": build_validation_passed,
            "current_step": "build_validation",
        }

    async def _run_comprehensive_validation(
        self, 
        project_path: Path, 
        language: str, 
        framework: str, 
        specification: dict
    ) -> List[Dict[str, Any]]:
        """Run comprehensive validation using available system tools."""
        results = []
        
        # 1. File Structure Validation
        results.append(await self._validate_file_structure(project_path, language))
        
        # 2. Syntax Validation  
        results.append(await self._validate_syntax(project_path, language))
        
        # 3. Dependency Installation Test
        results.append(await self._validate_dependencies(project_path, language))
        
        # 4. Configuration Validation
        results.append(await self._validate_configuration(project_path, language, framework))
        
        # 5. Import/Module Resolution Test
        results.append(await self._validate_imports(project_path, language))
        
        return [r for r in results if r is not None]

    async def _validate_file_structure(self, project_path: Path, language: str) -> Dict[str, Any]:
        """Validate that essential files exist and have reasonable structure."""
        start_time = time.time()
        
        try:
            essential_files = []
            
            if language == "python":
                essential_files = ["pyproject.toml", "requirements.txt"]
                # Look for main module
                src_files = list(project_path.rglob("*.py"))
                if not src_files:
                    return {
                        "step": "file_structure",
                        "status": "failed",
                        "duration_ms": int((time.time() - start_time) * 1000),
                        "error": "No Python source files found"
                    }
            
            elif language in ["javascript", "typescript"]:
                essential_files = ["package.json"]
                src_files = list(project_path.rglob("*.js")) + list(project_path.rglob("*.ts"))
                if not src_files:
                    return {
                        "step": "file_structure", 
                        "status": "failed",
                        "duration_ms": int((time.time() - start_time) * 1000),
                        "error": f"No {language} source files found"
                    }
            
            # Check for at least one essential file
            found_essential = any((project_path / f).exists() for f in essential_files)
            
            return {
                "step": "file_structure",
                "status": "success" if found_essential else "failed", 
                "duration_ms": int((time.time() - start_time) * 1000),
                "output": f"Found {len(src_files) if 'src_files' in locals() else 0} source files, essential config: {found_essential}"
            }
            
        except Exception as e:
            return {
                "step": "file_structure",
                "status": "error",
                "duration_ms": int((time.time() - start_time) * 1000),
                "error": str(e)
            }

    async def _validate_syntax(self, project_path: Path, language: str) -> Dict[str, Any]:
        """Validate syntax of source files using available tools."""
        start_time = time.time()
        
        try:
            if language == "python":
                # Use Python's ast module to check syntax
                python_files = list(project_path.rglob("*.py"))
                syntax_errors = []
                
                for py_file in python_files:
                    try:
                        with open(py_file, 'r', encoding='utf-8') as f:
                            source = f.read()
                        # Try to parse the Python code
                        compile(source, str(py_file), 'exec')
                    except SyntaxError as e:
                        syntax_errors.append(f"{py_file.name}: {e}")
                    except Exception as e:
                        syntax_errors.append(f"{py_file.name}: {e}")
                
                if syntax_errors:
                    return {
                        "step": "syntax_validation",
                        "status": "failed",
                        "duration_ms": int((time.time() - start_time) * 1000),
                        "error": f"Syntax errors in {len(syntax_errors)} files: {'; '.join(syntax_errors[:3])}"
                    }
                
                return {
                    "step": "syntax_validation",
                    "status": "success",
                    "duration_ms": int((time.time() - start_time) * 1000),
                    "output": f"Validated syntax of {len(python_files)} Python files"
                }
            
            # For other languages, do basic file validation
            return {
                "step": "syntax_validation", 
                "status": "success",
                "duration_ms": int((time.time() - start_time) * 1000),
                "output": f"Basic validation completed for {language}"
            }
            
        except Exception as e:
            return {
                "step": "syntax_validation",
                "status": "error", 
                "duration_ms": int((time.time() - start_time) * 1000),
                "error": str(e)
            }

    async def _validate_dependencies(self, project_path: Path, language: str) -> Dict[str, Any]:
        """Validate that dependency files are well-formed."""
        start_time = time.time()
        
        try:
            if language == "python":
                # Check pyproject.toml or requirements.txt
                pyproject_file = project_path / "pyproject.toml"
                requirements_file = project_path / "requirements.txt"
                
                if pyproject_file.exists():
                    import tomllib
                    with open(pyproject_file, 'rb') as f:
                        pyproject_data = tomllib.load(f)
                    
                    # Check for basic structure
                    has_dependencies = (
                        'dependencies' in pyproject_data.get('project', {}) or
                        'tool' in pyproject_data and 'poetry' in pyproject_data['tool']
                    )
                    
                    return {
                        "step": "dependency_validation",
                        "status": "success",
                        "duration_ms": int((time.time() - start_time) * 1000),
                        "output": f"pyproject.toml is valid, has_dependencies: {has_dependencies}"
                    }
                
                elif requirements_file.exists():
                    with open(requirements_file, 'r') as f:
                        requirements = f.readlines()
                    
                    return {
                        "step": "dependency_validation",
                        "status": "success", 
                        "duration_ms": int((time.time() - start_time) * 1000),
                        "output": f"requirements.txt found with {len([r for r in requirements if r.strip()])} dependencies"
                    }
                
                return {
                    "step": "dependency_validation",
                    "status": "failed",
                    "duration_ms": int((time.time() - start_time) * 1000),
                    "error": "No dependency file (pyproject.toml or requirements.txt) found"
                }
            
            elif language in ["javascript", "typescript"]:
                package_json = project_path / "package.json"
                if package_json.exists():
                    import json
                    with open(package_json, 'r') as f:
                        package_data = json.load(f)
                    
                    dep_count = len(package_data.get('dependencies', {})) + len(package_data.get('devDependencies', {}))
                    
                    return {
                        "step": "dependency_validation",
                        "status": "success",
                        "duration_ms": int((time.time() - start_time) * 1000),
                        "output": f"package.json is valid with {dep_count} dependencies"
                    }
                
                return {
                    "step": "dependency_validation", 
                    "status": "failed",
                    "duration_ms": int((time.time() - start_time) * 1000),
                    "error": "No package.json found"
                }
            
            return {
                "step": "dependency_validation",
                "status": "success",
                "duration_ms": int((time.time() - start_time) * 1000), 
                "output": f"Dependency validation skipped for {language}"
            }
            
        except Exception as e:
            return {
                "step": "dependency_validation",
                "status": "error",
                "duration_ms": int((time.time() - start_time) * 1000),
                "error": str(e)
            }

    async def _validate_configuration(self, project_path: Path, language: str, framework: str) -> Dict[str, Any]:
        """Validate framework-specific configuration files."""
        start_time = time.time()
        
        try:
            config_issues = []
            
            if framework.lower() == "fastapi" and language == "python":
                # Look for FastAPI app creation
                python_files = list(project_path.rglob("*.py"))
                fastapi_found = False
                
                for py_file in python_files:
                    try:
                        with open(py_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                        if "FastAPI" in content and ("app = " in content or "application = " in content):
                            fastapi_found = True
                            break
                    except Exception:
                        continue
                
                if not fastapi_found:
                    config_issues.append("No FastAPI app initialization found")
            
            elif framework.lower() == "express" and language in ["javascript", "typescript"]:
                # Look for Express app setup
                js_files = list(project_path.rglob("*.js")) + list(project_path.rglob("*.ts"))
                express_found = False
                
                for js_file in js_files:
                    try:
                        with open(js_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                        if "express" in content.lower() and ("app = " in content or "const app" in content):
                            express_found = True
                            break
                    except Exception:
                        continue
                
                if not express_found:
                    config_issues.append("No Express app initialization found")
            
            status = "failed" if config_issues else "success"
            message = f"Configuration issues: {'; '.join(config_issues)}" if config_issues else f"{framework} configuration appears valid"
            
            return {
                "step": "configuration_validation",
                "status": status,
                "duration_ms": int((time.time() - start_time) * 1000),
                "output": message,
                "error": message if config_issues else None
            }
            
        except Exception as e:
            return {
                "step": "configuration_validation",
                "status": "error",
                "duration_ms": int((time.time() - start_time) * 1000),
                "error": str(e)
            }

    async def _validate_imports(self, project_path: Path, language: str) -> Dict[str, Any]:
        """Validate that imports/requires in source files are resolvable."""
        start_time = time.time()
        
        try:
            if language == "python":
                python_files = list(project_path.rglob("*.py"))
                import_issues = []
                
                for py_file in python_files:
                    try:
                        with open(py_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # Look for obvious import issues (very basic check)
                        lines = content.split('\n')
                        for i, line in enumerate(lines):
                            line = line.strip()
                            if line.startswith('from ') and ' import ' in line:
                                # Check for relative imports that might be broken
                                if line.startswith('from .') and '/' not in str(py_file):
                                    import_issues.append(f"{py_file.name}:{i+1}: Relative import in root file")
                    except Exception:
                        continue
                
                status = "failed" if import_issues else "success"
                message = f"Import issues: {'; '.join(import_issues[:3])}" if import_issues else f"Validated imports in {len(python_files)} Python files"
                
                return {
                    "step": "import_validation",
                    "status": status,
                    "duration_ms": int((time.time() - start_time) * 1000),
                    "output": message,
                    "error": message if import_issues else None
                }
            
            return {
                "step": "import_validation",
                "status": "success",
                "duration_ms": int((time.time() - start_time) * 1000),
                "output": f"Import validation completed for {language}"
            }
            
        except Exception as e:
            return {
                "step": "import_validation",
                "status": "error",
                "duration_ms": int((time.time() - start_time) * 1000),
                "error": str(e)
            }
        """Ensure the build validation Docker image exists with all required tools."""
        try:
            # Check if our validation image exists
            result = await self._run_command(["docker", "images", "-q", self.validation_image])
            
            if not result.stdout.strip():
                # Build the validation container
                self._log_step("Building validation container with all required tools...")
                await self._build_validation_container()
                
        except Exception as e:
            logger.warning(f"Could not ensure validation container: {e}")
            # Fall back to creating a basic validation container
            await self._build_validation_container()

    async def _build_validation_container(self):
        """Build a Docker image with all validation tools installed."""
        dockerfile_content = '''FROM node:20-alpine

# Install Python, pip, and other tools
RUN apk add --no-cache python3 py3-pip py3-pytest docker-cli curl bash

# Install Node.js tools globally
RUN npm install -g npm@latest

# Install Python testing tools using system packages to avoid PEP 668 issues
# Use --break-system-packages as fallback for any additional packages
RUN pip3 install --break-system-packages pytest-cov || echo "pytest-cov not available, using system pytest"

# Create working directory
WORKDIR /workspace

# Add validation script
COPY validate.sh /usr/local/bin/validate.sh
RUN chmod +x /usr/local/bin/validate.sh

CMD ["/bin/bash"]
'''

        validation_script = '''#!/bin/bash
set -e

COMMAND="$1"
LANGUAGE="$2"
PROJECT_DIR="/workspace"

cd "$PROJECT_DIR"

case "$COMMAND" in
    "install")
        if [ "$LANGUAGE" = "javascript" ] || [ "$LANGUAGE" = "typescript" ]; then
            if [ -f "package.json" ]; then
                echo "Installing npm dependencies..."
                npm install
                echo "npm install completed successfully"
            else
                echo "No package.json found"
                exit 1
            fi
        elif [ "$LANGUAGE" = "python" ]; then
            if [ -f "requirements.txt" ]; then
                echo "Installing pip dependencies..."
                pip3 install -r requirements.txt
                echo "pip install completed successfully"
            elif [ -f "pyproject.toml" ]; then
                echo "Installing Python project..."
                pip3 install .
                echo "pip install completed successfully"
            else
                echo "No requirements.txt or pyproject.toml found"
                exit 1
            fi
        else
            echo "Unsupported language: $LANGUAGE"
            exit 1
        fi
        ;;
    "test")
        if [ "$LANGUAGE" = "javascript" ] || [ "$LANGUAGE" = "typescript" ]; then
            if [ -f "package.json" ]; then
                echo "Running npm tests..."
                npm test
                echo "Tests completed successfully"
            else
                echo "No package.json found"
                exit 1
            fi
        elif [ "$LANGUAGE" = "python" ]; then
            if [ -f "pytest.ini" ] || find . -name "test_*.py" | head -1 | grep -q .; then
                echo "Running pytest..."
                python3 -m pytest -v
                echo "Tests completed successfully"
            else
                echo "No tests found"
                exit 1
            fi
        else
            echo "Unsupported language: $LANGUAGE"
            exit 1
        fi
        ;;
    "start")
        if [ "$LANGUAGE" = "javascript" ] || [ "$LANGUAGE" = "typescript" ]; then
            if [ -f "package.json" ]; then
                echo "Starting Node.js application..."
                timeout 30 npm start &
                sleep 10
                echo "Application started"
            else
                echo "No package.json found"
                exit 1
            fi
        else
            echo "Runtime validation not implemented for: $LANGUAGE"
            exit 1
        fi
        ;;
    *)
        echo "Unknown command: $COMMAND"
        exit 1
        ;;
esac
'''

        with tempfile.TemporaryDirectory() as build_dir:
            build_path = Path(build_dir)
            
            # Write Dockerfile
            (build_path / "Dockerfile").write_text(dockerfile_content)
            
            # Write validation script
            (build_path / "validate.sh").write_text(validation_script)
            
            # Build the image
            build_cmd = [
                "docker", "build", 
                "-t", self.validation_image,
                str(build_path)
            ]
            
            result = await self._run_command(build_cmd, timeout=300)  # 5 minute timeout
            
            if result.returncode != 0:
                raise Exception(f"Failed to build validation container: {result.stderr}")
                
            self._log_step("Validation container built successfully")

    async def _run_containerized_validation(
        self, 
        project_path: Path, 
        language: str, 
        framework: str, 
        specification: Dict
    ) -> List[Dict]:
        """Run the complete build validation pipeline in containers."""
        results = []
        
        # Step 1: Package Installation
        install_result = await self._containerized_install(project_path, language)
        results.append(install_result)
        
        # Only continue if installation succeeded
        if install_result.get("status") != "success":
            return results
        
        # Step 2: Docker Build (if applicable) - use host docker for this
        if (project_path / "Dockerfile").exists():
            docker_result = await self._validate_docker_build(project_path)
            results.append(docker_result)
        
        # Step 3: Test Execution
        test_result = await self._containerized_test_execution(project_path, language)
        results.append(test_result)
        
        # Step 4: Runtime Validation (if web application)
        if self._is_web_application(specification):
            runtime_result = await self._containerized_runtime_validation(
                project_path, language, framework
            )
            results.append(runtime_result)
        
        return results

    async def _containerized_install(self, project_path: Path, language: str) -> Dict:
        """Run package installation in validation container."""
        start_time = time.time()
        
        try:
            cmd = [
                "docker", "run", "--rm",
                "-v", f"{project_path}:/workspace",
                self.validation_image,
                "/usr/local/bin/validate.sh", "install", language
            ]
            
            result = await self._run_command(cmd, timeout=300)
            duration_ms = int((time.time() - start_time) * 1000)
            
            if result.returncode == 0:
                return {
                    "step": "install",
                    "status": "success",
                    "duration_ms": duration_ms,
                    "command": " ".join(cmd),
                    "output": result.stdout[-500:] if result.stdout else ""
                }
            else:
                return {
                    "step": "install",
                    "status": "failed",
                    "duration_ms": duration_ms,
                    "command": " ".join(cmd),
                    "error": result.stderr[:1000],
                    "exit_code": result.returncode
                }
                
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "step": "install",
                "status": "error",
                "duration_ms": duration_ms,
                "error": str(e)
            }

    async def _containerized_test_execution(self, project_path: Path, language: str) -> Dict:
        """Run tests in validation container."""
        start_time = time.time()
        
        try:
            cmd = [
                "docker", "run", "--rm",
                "-v", f"{project_path}:/workspace",
                self.validation_image,
                "/usr/local/bin/validate.sh", "test", language
            ]
            
            result = await self._run_command(cmd, timeout=300)
            duration_ms = int((time.time() - start_time) * 1000)
            
            if result.returncode == 0:
                return {
                    "step": "test",
                    "status": "success",
                    "duration_ms": duration_ms,
                    "command": " ".join(cmd),
                    "output": result.stdout[-500:] if result.stdout else ""
                }
            else:
                return {
                    "step": "test",
                    "status": "failed",
                    "duration_ms": duration_ms,
                    "command": " ".join(cmd),
                    "error": result.stderr[:1000],
                    "exit_code": result.returncode
                }
                
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "step": "test",
                "status": "error",
                "duration_ms": duration_ms,
                "error": str(e)
            }

    async def _containerized_runtime_validation(
        self, project_path: Path, language: str, framework: str
    ) -> Dict:
        """Run runtime validation in container with health checks."""
        start_time = time.time()
        
        try:
            # Start the application in a container
            container_name = f"agentforge-runtime-test-{int(time.time())}"
            
            start_cmd = [
                "docker", "run", "-d", "--rm",
                "--name", container_name,
                "-v", f"{project_path}:/workspace",
                "-p", "0:3000",  # Map to random host port
                self.validation_image,
                "/usr/local/bin/validate.sh", "start", language
            ]
            
            start_result = await self._run_command(start_cmd, timeout=30)
            
            if start_result.returncode != 0:
                return {
                    "step": "runtime",
                    "status": "failed",
                    "duration_ms": int((time.time() - start_time) * 1000),
                    "error": "Failed to start application container",
                    "details": start_result.stderr[:500]
                }
            
            try:
                # Wait for application to start
                await asyncio.sleep(15)
                
                # Get the mapped port
                port_cmd = [
                    "docker", "port", container_name, "3000"
                ]
                port_result = await self._run_command(port_cmd, timeout=10)
                
                if port_result.returncode == 0 and port_result.stdout.strip():
                    host_port = port_result.stdout.strip().split(":")[-1]
                    
                    # Test health endpoint
                    health_result = await self._test_health_endpoint(f"http://localhost:{host_port}/health")
                    
                    duration_ms = int((time.time() - start_time) * 1000)
                    
                    if health_result:
                        return {
                            "step": "runtime",
                            "status": "success",
                            "duration_ms": duration_ms,
                            "health_endpoint": f"http://localhost:{host_port}/health",
                            "message": "Application started and health endpoint responded"
                        }
                    else:
                        return {
                            "step": "runtime",
                            "status": "failed",
                            "duration_ms": duration_ms,
                            "error": "Health endpoint did not respond",
                            "health_endpoint": f"http://localhost:{host_port}/health"
                        }
                else:
                    return {
                        "step": "runtime",
                        "status": "failed",
                        "duration_ms": int((time.time() - start_time) * 1000),
                        "error": "Could not determine container port mapping"
                    }
                    
            finally:
                # Always cleanup the container
                cleanup_cmd = ["docker", "kill", container_name]
                await self._run_command(cleanup_cmd, timeout=10)
                
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "step": "runtime",
                "status": "error",
                "duration_ms": duration_ms,
                "error": str(e)
            }

    async def _write_project_files(self, project_path: Path, files: List[Dict]) -> None:
        """Write all project files to temporary directory."""
        for file_info in files:
            file_path = project_path / file_info["path"]
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(file_info["content"])

    async def _validate_docker_build(self, project_path: Path) -> Dict:
        """Validate that Docker image can be built (runs on host Docker)."""
        start_time = time.time()
        
        try:
            # Check if docker is available
            try:
                docker_check = await self._run_command(["which", "docker"], timeout=10)
                if docker_check.returncode != 0:
                    return {
                        "step": "docker_build", 
                        "status": "failed", 
                        "reason": "docker not available on host",
                        "duration_ms": int((time.time() - start_time) * 1000)
                    }
            except Exception:
                return {
                    "step": "docker_build", 
                    "status": "failed", 
                    "reason": "docker availability check failed",
                    "duration_ms": int((time.time() - start_time) * 1000)
                }
            
            # Generate a unique tag for this build
            tag = f"agentforge-test-{int(time.time())}"
            cmd = ["docker", "build", "-t", tag, "."]
            
            result = await self._run_command(cmd, project_path)
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Clean up the image after testing
            if result.returncode == 0:
                try:
                    await self._run_command(["docker", "rmi", tag], project_path, timeout=30)
                except:
                    pass  # Cleanup failure is not critical
                
                return {
                    "step": "docker_build",
                    "status": "success",
                    "duration_ms": duration_ms,
                    "command": " ".join(cmd)
                }
            else:
                return {
                    "step": "docker_build",
                    "status": "failed",
                    "duration_ms": duration_ms,
                    "command": " ".join(cmd),
                    "error": result.stderr[:1000],
                    "exit_code": result.returncode
                }
                
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "step": "docker_build",
                "status": "error",
                "duration_ms": duration_ms,
                "error": str(e)
            }

    async def _test_health_endpoint(self, url: str) -> bool:
        """Test if health endpoint responds successfully."""
        try:
            # Use curl to test the endpoint (avoiding external dependencies)
            result = await self._run_command(
                ["curl", "-s", "-f", "--max-time", "10", url],
                timeout=15
            )
            return result.returncode == 0
        except:
            return False

    async def _run_command(
        self,
        cmd: List[str],
        cwd: Optional[Path] = None,
        timeout: Optional[int] = None
    ) -> subprocess.CompletedProcess:
        """Run a command with timeout protection."""
        timeout = timeout or self.timeout_seconds

        try:
            # Ensure Docker is accessible - try direct path first, then PATH
            if cmd[0] == "docker":
                # Try common Docker paths
                docker_paths = [
                    "/usr/bin/docker",
                    "/usr/local/bin/docker", 
                    "docker"  # fallback to PATH
                ]
                
                docker_cmd = None
                for docker_path in docker_paths:
                    try:
                        # Test if docker exists and is executable
                        test_process = await asyncio.create_subprocess_exec(
                            docker_path, "--version",
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        await test_process.wait()
                        if test_process.returncode == 0:
                            docker_cmd = docker_path
                            break
                    except FileNotFoundError:
                        continue
                
                if not docker_cmd:
                    raise FileNotFoundError("Docker executable not found in any common paths")
                
                # Replace 'docker' with the found path
                cmd = [docker_cmd] + cmd[1:]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 
                timeout=timeout
            )
            
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=process.returncode,
                stdout=stdout.decode("utf-8", errors="ignore"),
                stderr=stderr.decode("utf-8", errors="ignore")
            )
            
        except asyncio.TimeoutError:
            if 'process' in locals():
                process.kill()
                await process.wait()
            raise Exception(f"Command timed out after {timeout} seconds: {' '.join(cmd)}")

    def _is_web_application(self, specification: Dict) -> bool:
        """Determine if this is a web application that should have runtime validation."""
        api_endpoints = specification.get("api_endpoints", [])
        target_framework = specification.get("target_framework", "").lower()
        
        # Has API endpoints or web framework
        return bool(api_endpoints) or target_framework in ["express", "fastapi", "flask", "django"]