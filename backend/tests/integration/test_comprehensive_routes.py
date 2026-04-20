"""
Comprehensive tests for API routes to improve coverage.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
from httpx import AsyncClient

from app.models.auth import User, UserRole


@pytest.mark.asyncio
class TestAuthRoutes:
    """Test authentication API routes."""
    
    async def test_register_success(self, client: AsyncClient, mock_email_service):
        """Test successful user registration."""
        user_data = {
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "TestPassword123!",
            "full_name": "New User"
        }
        
        response = await client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 201
        
        data = response.json()
        assert data["email"] == user_data["email"]
        assert data["username"] == user_data["username"]
        assert "id" in data

    async def test_register_duplicate_email(self, client: AsyncClient, test_user):
        """Test registration with duplicate email."""
        user_data = {
            "email": test_user.email,
            "username": "different",
            "password": "TestPassword123!",
            "full_name": "Different User"
        }
        
        response = await client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 400
        
    async def test_register_weak_password(self, client: AsyncClient):
        """Test registration with weak password."""
        user_data = {
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "weak",
            "full_name": "New User"
        }
        
        response = await client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 422

    async def test_login_success(self, client: AsyncClient, test_user):
        """Test successful login."""
        login_data = {
            "email": test_user.email,
            "password": "testpassword123"
        }
        
        response = await client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_invalid_credentials(self, client: AsyncClient, test_user):
        """Test login with invalid credentials."""
        login_data = {
            "email": test_user.email,
            "password": "wrongpassword"
        }
        
        response = await client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 401

    async def test_get_current_user(self, client: AsyncClient, auth_headers):
        """Test getting current user."""
        response = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "id" in data
        assert "email" in data

    async def test_get_current_user_unauthorized(self, client: AsyncClient):
        """Test getting current user without authentication."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    async def test_send_verification_email(
        self, client: AsyncClient, auth_headers, mock_email_service, test_user
    ):
        """Test sending verification email."""
        response = await client.post(
            "/api/v1/auth/verify/send",
            json={"email": test_user.email},
            headers=auth_headers,
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True

    async def test_verify_email_token(self, client: AsyncClient, db_session, test_user):
        """Test email verification with token."""
        from app.services.auth import auth_service
        
        # Create verification token
        token = await auth_service.create_verification_token(db_session, test_user)
        
        response = await client.post(
            "/api/v1/auth/verify/confirm",
            json={"token": token}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["is_verified"] is True

    async def test_verify_email_invalid_token(self, client: AsyncClient):
        """Test email verification with invalid token."""
        response = await client.post(
            "/api/v1/auth/verify/confirm",
            json={"token": "invalid-token"}
        )
        assert response.status_code == 400

    async def test_refresh_token(self, client: AsyncClient, test_user, test_refresh_token):
        """Test token refresh."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": test_refresh_token._test_token_value}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "access_token" in data

    async def test_refresh_invalid_token(self, client: AsyncClient):
        """Test refresh with invalid token."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-token"}
        )
        assert response.status_code == 401

    async def test_logout(self, client: AsyncClient, auth_headers, test_refresh_token):
        """Test user logout (requires refresh token body to revoke)."""
        response = await client.post(
            "/api/v1/auth/logout",
            headers=auth_headers,
            json={"refresh_token": test_refresh_token._test_token_value},
        )
        assert response.status_code == 200

    async def test_api_key_authentication(self, client: AsyncClient, test_api_key):
        """Test API key authentication."""
        headers = {"X-API-Key": test_api_key._test_key_value}
        
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 200

    async def test_api_key_invalid(self, client: AsyncClient):
        """Test invalid API key."""
        headers = {"X-API-Key": "invalid-key"}
        
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401


@pytest.mark.asyncio
class TestProjectRoutes:
    """Test project management API routes."""
    
    async def test_create_project_success(self, client: AsyncClient, auth_headers, sample_project_data, mock_orchestrator):
        """Test successful project creation."""
        with patch("app.api.routes.projects.get_orchestrator", return_value=mock_orchestrator):
            response = await client.post(
                "/api/v1/projects/",
                json=sample_project_data,
                headers=auth_headers
            )
            assert response.status_code == 201
            
            data = response.json()
            assert data["name"] == sample_project_data["name"]
            assert "id" in data

    async def test_create_project_unauthorized(self, client: AsyncClient, sample_project_data):
        """Test project creation without authentication."""
        response = await client.post("/api/v1/projects/", json=sample_project_data)
        assert response.status_code == 401

    async def test_list_projects(self, client: AsyncClient, auth_headers):
        """Test listing user projects."""
        response = await client.get("/api/v1/projects/", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)

    async def test_get_project_success(self, client: AsyncClient, auth_headers, db_session, test_user):
        """Test getting project details."""
        # Create a test project
        from app.models.project import Project, ProjectStatus
        
        project = Project(
            id=uuid.uuid4(),
            user_id=test_user.id,
            name="Test Project",
            description="Test Description",
            requirements="Test requirements",
            target_language="Python",
            target_framework="FastAPI",
            status=ProjectStatus.PENDING,
        )
        db_session.add(project)
        await db_session.commit()
        
        response = await client.get(f"/api/v1/projects/{project.id}", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == str(project.id)

    async def test_get_project_not_found(self, client: AsyncClient, auth_headers):
        """Test getting non-existent project."""
        fake_id = uuid.uuid4()
        response = await client.get(f"/api/v1/projects/{fake_id}", headers=auth_headers)
        assert response.status_code == 404

    async def test_start_project_run(self, client: AsyncClient, auth_headers, db_session, test_user, mock_orchestrator):
        """Test starting project run."""
        from app.models.project import Project, ProjectStatus
        
        project = Project(
            id=uuid.uuid4(),
            user_id=test_user.id,
            name="Test Project",
            description="Test Description",
            requirements="Test requirements",
            target_language="Python",
            target_framework="FastAPI",
            status=ProjectStatus.PENDING,
        )
        db_session.add(project)
        await db_session.commit()
        
        with patch("app.api.routes.projects.get_orchestrator", return_value=mock_orchestrator):
            response = await client.post(
                f"/api/v1/projects/{project.id}/runs",
                headers=auth_headers,
            )
            assert response.status_code == 201

    async def test_health_endpoint(self, client: AsyncClient):
        """Test health check endpoint."""
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"


@pytest.mark.asyncio  
class TestArtifactRoutes:
    """Test artifact management API routes."""
    
    async def test_get_project_artifacts_unauthorized(self, client: AsyncClient):
        """Test getting project artifacts without authentication."""
        fake_id = uuid.uuid4()
        response = await client.get(f"/api/v1/artifacts/project/{fake_id}")
        assert response.status_code == 401

    async def test_get_project_artifacts_not_found(self, client: AsyncClient, auth_headers):
        """Test getting artifacts for non-existent project."""
        fake_id = uuid.uuid4()
        response = await client.get(f"/api/v1/artifacts/project/{fake_id}", headers=auth_headers)
        assert response.status_code == 404

    async def test_get_artifact_content_unauthorized(self, client: AsyncClient):
        """Test getting artifact content without authentication."""
        fake_artifact_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/artifacts/{fake_artifact_id}/content")
        assert response.status_code == 401


@pytest.mark.asyncio
class TestSecurityAndValidation:
    """Test security and input validation."""
    
    async def test_malformed_json_request(self, client: AsyncClient):
        """Test handling of malformed JSON."""
        response = await client.post(
            "/api/v1/auth/login",
            content="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    async def test_missing_required_fields(self, client: AsyncClient):
        """Test validation of required fields."""
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com"}  # Missing required fields
        )
        assert response.status_code == 422

    async def test_invalid_uuid_format(self, client: AsyncClient, auth_headers):
        """Test handling of invalid UUID format."""
        response = await client.get("/api/v1/projects/invalid-uuid", headers=auth_headers)
        assert response.status_code == 422

    async def test_sql_injection_protection(self, client: AsyncClient):
        """Test SQL injection protection."""
        malicious_input = {"email": "'; DROP TABLE users; --", "password": "test"}
        
        response = await client.post("/api/v1/auth/login", json=malicious_input)
        # Should not crash and return proper error
        assert response.status_code in [400, 401, 422]

    async def test_xss_protection(self, client: AsyncClient, auth_headers):
        """Test XSS protection in inputs."""
        xss_input = {
            "name": "<script>alert('xss')</script>",
            "description": "Normal description",
            "requirements": "Normal requirements",
            "target_language": "Python",
            "target_framework": "FastAPI"
        }
        
        response = await client.post("/api/v1/projects/", json=xss_input, headers=auth_headers)
        # Should either sanitize input or return validation error
        assert response.status_code in [201, 400, 422]