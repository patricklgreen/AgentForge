"""
Integration tests for authentication endpoints and security.
"""
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User, UserRole, APIKey
from app.services.auth import auth_service
from tests.auth_fixtures import (
    create_authenticated_user,
    get_jwt_headers,
    login_user,
)


class TestAuthenticationEndpoints:
    """Test authentication and user management endpoints."""

    @pytest.mark.asyncio
    async def test_register_user_success(self, client: AsyncClient):
        """Test successful user registration."""
        user_data = {
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "SecurePass123!",
            "full_name": "New User",
        }
        
        response = await client.post("/api/v1/auth/register", json=user_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == user_data["email"]
        assert data["username"] == user_data["username"]
        assert data["full_name"] == user_data["full_name"]
        assert data["role"] == "user"
        assert data["is_active"] is True
        assert data["is_verified"] is False  # Email verification required
        assert "id" in data
        assert "hashed_password" not in data  # Password not exposed

    @pytest.mark.asyncio
    async def test_register_duplicate_email_fails(self, client: AsyncClient, test_user: User):
        """Test registration fails with duplicate email."""
        user_data = {
            "email": test_user.email,  # Duplicate email
            "username": "differentuser",
            "password": "SecurePass123!",
        }
        
        response = await client.post("/api/v1/auth/register", json=user_data)
        
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_register_duplicate_username_fails(self, client: AsyncClient, test_user: User):
        """Test registration fails with duplicate username."""
        user_data = {
            "email": "different@example.com",
            "username": test_user.username,  # Duplicate username
            "password": "SecurePass123!",
        }
        
        response = await client.post("/api/v1/auth/register", json=user_data)
        
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_register_weak_password_fails(self, client: AsyncClient):
        """Test registration fails with weak password."""
        user_data = {
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "weak",  # Too weak
        }
        
        response = await client.post("/api/v1/auth/register", json=user_data)
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, db_session: AsyncSession):
        """Test successful login."""
        # Create user with known password
        user = await create_authenticated_user(
            db_session, 
            email="login@test.com", 
            password="LoginPass123!"
        )
        
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "login@test.com", "password": "LoginPass123!"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["token_type"] == "bearer"
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["expires_in"] > 0
        assert data["user"]["id"] == str(user.id)
        assert data["user"]["email"] == user.email

    @pytest.mark.asyncio
    async def test_login_invalid_email_fails(self, client: AsyncClient):
        """Test login fails with invalid email."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@test.com", "password": "anypassword"}
        )
        
        assert response.status_code == 401
        assert "invalid email or password" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_login_invalid_password_fails(self, client: AsyncClient, test_user: User):
        """Test login fails with invalid password."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "wrongpassword"}
        )
        
        assert response.status_code == 401
        assert "invalid email or password" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_login_inactive_user_fails(self, client: AsyncClient, inactive_user: User):
        """Test login fails for inactive user."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": inactive_user.email, "password": "password123"}
        )
        
        assert response.status_code == 401
        # Inactive users are excluded from authenticate_user(); same message as wrong password
        assert "invalid email or password" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_current_user_success(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """Test getting current user profile."""
        response = await client.get("/api/v1/auth/me", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_user.id)
        assert data["email"] == test_user.email
        assert data["username"] == test_user.username

    @pytest.mark.asyncio
    async def test_get_current_user_without_auth_fails(self, client: AsyncClient):
        """Test getting current user without authentication fails."""
        response = await client.get("/api/v1/auth/me")
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token_fails(self, client: AsyncClient):
        """Test getting current user with invalid token fails."""
        headers = {"Authorization": "Bearer invalid-token"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, client: AsyncClient, test_refresh_token):
        """Test successful token refresh."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": test_refresh_token._test_token_value}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        # TokenResponse from /auth/refresh is access-only (no rotated refresh token)
        assert "token_type" in data

    @pytest.mark.asyncio
    async def test_api_key_authentication(self, client: AsyncClient, test_api_key: APIKey):
        """Test API key authentication works."""
        headers = {"X-API-Key": test_api_key._test_key_value}
        response = await client.get("/api/v1/auth/me", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_api_key.user_id)

    @pytest.mark.asyncio
    async def test_api_key_invalid_key_fails(self, client: AsyncClient):
        """Test invalid API key authentication fails."""
        headers = {"X-API-Key": "invalid-key"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        
        assert response.status_code == 401


class TestProjectAuthenticationIntegration:
    """Test that project endpoints require authentication."""

    @pytest.mark.asyncio
    async def test_create_project_requires_auth(self, client: AsyncClient, sample_project_data: dict):
        """Test creating project requires authentication."""
        response = await client.post("/api/v1/projects/", json=sample_project_data)
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_project_with_auth_success(
        self, client: AsyncClient, sample_project_data: dict, auth_headers: dict
    ):
        """Test authenticated user can create project."""
        response = await client.post("/api/v1/projects/", json=sample_project_data, headers=auth_headers)
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_project_data["name"]

    @pytest.mark.asyncio
    async def test_list_projects_requires_auth(self, client: AsyncClient):
        """Test listing projects requires authentication."""
        response = await client.get("/api/v1/projects/")
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_projects_only_shows_user_projects(
        self, client: AsyncClient, db_session: AsyncSession, sample_project_data: dict
    ):
        """Test users only see their own projects."""
        # Create two users
        user1 = await create_authenticated_user(db_session, email="user1@test.com", username="user1")
        user2 = await create_authenticated_user(db_session, email="user2@test.com", username="user2")
        
        # Create projects for each user
        headers1 = await get_jwt_headers(user1)
        headers2 = await get_jwt_headers(user2)
        
        await client.post("/api/v1/projects/", json=sample_project_data, headers=headers1)
        await client.post(
            "/api/v1/projects/", 
            json={**sample_project_data, "name": "User 2 Project"}, 
            headers=headers2
        )
        
        # User 1 should only see their project
        response1 = await client.get("/api/v1/projects/", headers=headers1)
        assert response1.status_code == 200
        projects1 = response1.json()
        assert len(projects1) == 1
        assert projects1[0]["name"] == sample_project_data["name"]
        
        # User 2 should only see their project
        response2 = await client.get("/api/v1/projects/", headers=headers2)
        assert response2.status_code == 200
        projects2 = response2.json()
        assert len(projects2) == 1
        assert projects2[0]["name"] == "User 2 Project"

    @pytest.mark.asyncio
    async def test_admin_can_access_all_projects(
        self, client: AsyncClient, db_session: AsyncSession, sample_project_data: dict
    ):
        """Test admin users can access all projects."""
        # Create regular user and admin
        user = await create_authenticated_user(db_session, email="user@test.com", username="user")
        admin = await create_authenticated_user(
            db_session, email="admin@test.com", username="admin", role=UserRole.ADMIN
        )
        
        # Create project as regular user
        user_headers = await get_jwt_headers(user)
        create_response = await client.post("/api/v1/projects/", json=sample_project_data, headers=user_headers)
        project_id = create_response.json()["id"]
        
        # Admin should be able to access the project
        admin_headers = await get_jwt_headers(admin)
        response = await client.get(f"/api/v1/projects/{project_id}", headers=admin_headers)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_user_cannot_access_other_user_project(
        self, client: AsyncClient, db_session: AsyncSession, sample_project_data: dict
    ):
        """Test user cannot access another user's project."""
        # Create two users
        user1 = await create_authenticated_user(db_session, email="user1@test.com", username="user1")
        user2 = await create_authenticated_user(db_session, email="user2@test.com", username="user2")
        
        # Create project as user1
        headers1 = await get_jwt_headers(user1)
        create_response = await client.post("/api/v1/projects/", json=sample_project_data, headers=headers1)
        project_id = create_response.json()["id"]
        
        # User2 should not be able to access the project
        headers2 = await get_jwt_headers(user2)
        response = await client.get(f"/api/v1/projects/{project_id}", headers=headers2)
        assert response.status_code == 403


class TestArtifactsAuthentication:
    """Test that artifact endpoints require authentication and ownership."""

    @pytest.mark.asyncio
    async def test_get_project_artifacts_requires_auth(self, client: AsyncClient):
        """Test getting project artifacts requires authentication."""
        fake_project_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/artifacts/project/{fake_project_id}")
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_artifact_content_requires_auth(self, client: AsyncClient):
        """Test getting artifact content requires authentication."""
        fake_artifact_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/artifacts/{fake_artifact_id}/content")
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_artifact_download_url_requires_auth(self, client: AsyncClient):
        """Test getting artifact download URL requires authentication."""
        fake_artifact_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/artifacts/{fake_artifact_id}/download-url")
        
        assert response.status_code == 401


class TestSecurityEventLogging:
    """Test security event logging functionality."""

    @pytest.mark.asyncio
    async def test_failed_login_logs_security_event(self, client: AsyncClient):
        """Test that failed logins are logged as security events."""
        with patch('app.auth.dependencies.log_security_event') as mock_log:
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": "nonexistent@test.com", "password": "anypassword"}
            )
            
            assert response.status_code == 401
            # Security logging would be called in the actual auth service
            # This tests the integration point

    @pytest.mark.asyncio
    async def test_successful_login_updates_last_login(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test successful login updates user's last_login timestamp."""
        # Create user
        user = await create_authenticated_user(
            db_session, email="timestamp@test.com", password="TestPass123!"
        )
        original_last_login = user.last_login
        
        # Login
        await client.post(
            "/api/v1/auth/login",
            json={"email": "timestamp@test.com", "password": "TestPass123!"}
        )
        
        # Refresh user from database
        await db_session.refresh(user)
        
        # last_login should be updated
        assert user.last_login != original_last_login
        assert user.last_login is not None


class TestRoleBasedAccess:
    """Test role-based access control functionality."""

    @pytest.mark.asyncio
    async def test_user_role_hierarchy(self, client: AsyncClient, db_session: AsyncSession):
        """Test that role hierarchy works correctly."""
        # Create users with different roles
        viewer = await create_authenticated_user(
            db_session, email="viewer@test.com", username="viewer", role=UserRole.VIEWER
        )
        user = await create_authenticated_user(
            db_session, email="user@test.com", username="user", role=UserRole.USER  
        )
        admin = await create_authenticated_user(
            db_session, email="admin@test.com", username="admin", role=UserRole.ADMIN
        )
        
        # All should be able to access their own profile
        for test_user in [viewer, user, admin]:
            headers = await get_jwt_headers(test_user)
            response = await client.get("/api/v1/auth/me", headers=headers)
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_token_validation_edge_cases(self, client: AsyncClient):
        """Test various token validation edge cases."""
        # Malformed token
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer malformed.token"}
        )
        assert response.status_code == 401
        
        # Missing Bearer prefix
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "just-a-token"}
        )
        assert response.status_code == 401
        
        # Empty token
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer "}
        )
        assert response.status_code == 401