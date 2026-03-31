"""
Unit tests for authentication services and dependencies.
"""
import uuid
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.auth import User, UserRole
from app.services.auth import auth_service, AuthenticationError
from app.schemas.auth import JWTPayload


class TestAuthService:
    """Test authentication service functions."""

    def test_hash_password(self):
        """Test password hashing."""
        password = "test_pass123"
        hashed = auth_service.hash_password(password)
        
        assert hashed != password
        assert len(hashed) > 0
        assert auth_service.verify_password(password, hashed)

    def test_verify_password_success(self):
        """Test successful password verification."""
        password = "test_pass123"
        hashed = auth_service.hash_password(password)
        
        assert auth_service.verify_password(password, hashed) is True

    def test_verify_password_failure(self):
        """Test failed password verification."""
        password = "test_pass123"
        wrong_password = "wrong_pass"
        hashed = auth_service.hash_password(password)
        
        assert auth_service.verify_password(wrong_password, hashed) is False

    def test_create_access_token(self):
        """Test access token creation."""
        user = User(
            id=uuid.uuid4(),
            email="test@example.com", 
            username="test",
            role=UserRole.USER
        )
        token = auth_service.create_access_token(user)
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Token should be verifiable
        payload = auth_service.verify_jwt_token(token)
        assert payload.sub == str(user.id)

    def test_verify_jwt_token_success(self):
        """Test successful JWT token verification."""
        user = User(
            id=uuid.uuid4(),
            email="test@example.com", 
            username="test",
            role=UserRole.USER
        )
        token = auth_service.create_access_token(user)
        
        payload = auth_service.verify_jwt_token(token)
        
        assert isinstance(payload, JWTPayload)
        assert payload.sub == str(user.id)
        assert payload.type == "access"

    def test_verify_jwt_token_invalid(self):
        """Test JWT token verification with invalid token."""
        with pytest.raises((AuthenticationError, Exception)):
            auth_service.verify_jwt_token("invalid.token.here")

    def test_create_refresh_token(self):
        """Test refresh token creation."""
        token_value, token_hash = auth_service.create_refresh_token()
        
        assert isinstance(token_value, str)
        assert isinstance(token_hash, str)
        assert len(token_value) > 0
        assert len(token_hash) > 0
        assert token_value != token_hash

    def test_check_user_role(self):
        """Test user role checking."""
        admin_user = User(role=UserRole.ADMIN)
        regular_user = User(role=UserRole.USER)
        viewer_user = User(role=UserRole.VIEWER)
        
        # Admin can access anything
        assert auth_service.check_user_role(admin_user, UserRole.ADMIN) is True
        assert auth_service.check_user_role(admin_user, UserRole.USER) is True
        assert auth_service.check_user_role(admin_user, UserRole.VIEWER) is True
        
        # User can access user and viewer
        assert auth_service.check_user_role(regular_user, UserRole.ADMIN) is False
        assert auth_service.check_user_role(regular_user, UserRole.USER) is True
        assert auth_service.check_user_role(regular_user, UserRole.VIEWER) is True
        
        # Viewer can only access viewer
        assert auth_service.check_user_role(viewer_user, UserRole.ADMIN) is False
        assert auth_service.check_user_role(viewer_user, UserRole.USER) is False
        assert auth_service.check_user_role(viewer_user, UserRole.VIEWER) is True

    def test_check_resource_access_owner(self):
        """Test resource access check for resource owner."""
        user_id = uuid.uuid4()
        resource_user_id = user_id  # Same user
        user = User(id=user_id, role=UserRole.USER)
        
        result = auth_service.check_resource_access(user, resource_user_id)
        assert result is True

    def test_check_resource_access_admin(self):
        """Test resource access check for admin user."""
        user_id = uuid.uuid4()
        resource_user_id = uuid.uuid4()  # Different user
        admin_user = User(id=user_id, role=UserRole.ADMIN)
        
        result = auth_service.check_resource_access(admin_user, resource_user_id)
        assert result is True

    def test_check_resource_access_denied(self):
        """Test resource access denied for different user."""
        user_id = uuid.uuid4()
        resource_user_id = uuid.uuid4()  # Different user
        regular_user = User(id=user_id, role=UserRole.USER)
        
        result = auth_service.check_resource_access(regular_user, resource_user_id)
        assert result is False