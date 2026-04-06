"""
Unit tests for authentication services and dependencies.
"""
import uuid
from datetime import timedelta, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from jose import jwt

from app.models.auth import User, UserRole, APIKey
from app.services.auth import auth_service, AuthenticationError, AuthorizationError
from app.schemas.auth import JWTPayload


@pytest.mark.usefixtures("mock_email_service")
class TestAuthService:
    """Test authentication service functions."""

    def test_hash_password(self):
        """Test password hashing."""
        password = "TestPass123"
        hashed = auth_service.hash_password(password)
        
        assert hashed != password
        assert len(hashed) > 0
        assert auth_service.verify_password(password, hashed)

    def test_verify_password_success(self):
        """Test successful password verification."""
        password = "TestPass123"
        hashed = auth_service.hash_password(password)
        
        assert auth_service.verify_password(password, hashed) is True

    def test_verify_password_failure(self):
        """Test failed password verification."""
        password = "TestPass123"
        wrong_password = "WrongPass456"
        hashed = auth_service.hash_password(password)
        
        assert auth_service.verify_password(wrong_password, hashed) is False

    def test_verify_password_exception_handling(self):
        """Test password verification handles exceptions."""
        # Invalid hash should return False, not raise exception
        assert auth_service.verify_password("password", "invalid_hash") is False

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

    def test_create_access_token_with_custom_expiry(self):
        """Test access token creation with custom expiry."""
        user = User(
            id=uuid.uuid4(),
            email="test@example.com", 
            username="test",
            role=UserRole.USER
        )
        expires_delta = timedelta(hours=2)
        
        token = auth_service.create_access_token(user, expires_delta)
        
        assert isinstance(token, str)
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
        assert payload.email == user.email

    def test_verify_jwt_token_invalid(self):
        """Test JWT token verification with invalid token."""
        with pytest.raises((AuthenticationError, Exception)):
            auth_service.verify_jwt_token("invalid.token.here")

    def test_verify_jwt_token_expired(self):
        """Test JWT token verification with expired token."""
        user = User(
            id=uuid.uuid4(),
            email="test@example.com", 
            username="test",
            role=UserRole.USER
        )
        
        # Create token that expires immediately
        expires_delta = timedelta(seconds=-1)
        token = auth_service.create_access_token(user, expires_delta)
        
        with pytest.raises((AuthenticationError, Exception)):
            auth_service.verify_jwt_token(token)

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
        
        # User can access user and viewer but not admin
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

    def test_generate_api_key(self):
        """Test API key generation."""
        key_value, key_hash, key_prefix = auth_service.generate_api_key()
        
        assert isinstance(key_value, str)
        assert isinstance(key_hash, str) 
        assert isinstance(key_prefix, str)
        assert len(key_value) > 0
        assert len(key_hash) > 0
        assert len(key_prefix) > 0
        assert key_value != key_hash
        assert key_value.startswith(key_prefix)

    def test_api_key_scopes_check(self):
        """Test API key scope checking."""
        # Mock API key with scopes stored as JSON string
        api_key = MagicMock(spec=APIKey)
        api_key.scopes = '["read:projects", "write:projects"]'  # JSON string format
        
        # Should allow required scopes that exist
        assert auth_service.check_api_key_scopes(api_key, ["read:projects"]) is True
        assert auth_service.check_api_key_scopes(api_key, ["read:projects", "write:projects"]) is True
        
        # Should deny scopes that don't exist
        assert auth_service.check_api_key_scopes(api_key, ["admin:users"]) is False
        assert auth_service.check_api_key_scopes(api_key, ["read:projects", "admin:users"]) is False

    def test_api_key_scopes_empty(self):
        """Test API key scope checking with empty scopes."""
        api_key = MagicMock(spec=APIKey)
        api_key.scopes = None  # No scopes
        
        assert auth_service.check_api_key_scopes(api_key, ["read:projects"]) is False
        assert auth_service.check_api_key_scopes(api_key, []) is False  # No scopes means no access

    def test_api_key_scopes_invalid_json(self):
        """Test API key scope checking with invalid JSON."""
        api_key = MagicMock(spec=APIKey)
        api_key.scopes = "invalid json"
        
        assert auth_service.check_api_key_scopes(api_key, ["read:projects"]) is False

    def test_extract_user_agent(self):
        """Test user agent extraction from headers."""
        headers = {"user-agent": "Mozilla/5.0 (Test Browser)"}
        result = auth_service.extract_user_agent(headers)
        assert result == "Mozilla/5.0 (Test Browser)"
        
        # Test with no user agent
        headers_empty = {}
        result = auth_service.extract_user_agent(headers_empty)
        assert result is None

    def test_extract_ip_address(self):
        """Test IP address extraction from headers."""
        # Test X-Forwarded-For header (most common)
        headers = {"x-forwarded-for": "203.0.113.1, 198.51.100.2"}
        result = auth_service.extract_ip_address(headers)
        assert result == "203.0.113.1"  # Should return first IP
        
        # Test X-Real-IP header
        headers = {"x-real-ip": "203.0.113.5"}
        result = auth_service.extract_ip_address(headers)
        assert result == "203.0.113.5"
        
        # Test no headers
        headers_empty = {}
        result = auth_service.extract_ip_address(headers_empty)
        assert result is None

    def test_jwt_payload_structure(self):
        """Test JWT payload contains all required fields."""
        user = User(
            id=uuid.uuid4(),
            email="test@example.com",
            username="testuser",
            role=UserRole.USER
        )
        
        token = auth_service.create_access_token(user)
        payload = auth_service.verify_jwt_token(token)
        
        assert payload.sub == str(user.id)
        assert payload.email == user.email
        assert payload.username == user.username
        assert payload.role == user.role
        assert payload.exp > datetime.now(timezone.utc).timestamp()
        assert payload.iat <= datetime.now(timezone.utc).timestamp()
        assert payload.jti is not None

    def test_password_hash_different_each_time(self):
        """Test that password hashing produces different hashes each time."""
        password = "SamePassword123"
        hash1 = auth_service.hash_password(password)
        hash2 = auth_service.hash_password(password)
        
        assert hash1 != hash2  # Should be different due to salt
        assert auth_service.verify_password(password, hash1)
        assert auth_service.verify_password(password, hash2)

    @pytest.mark.asyncio
    async def test_create_user(self, db_session, mock_email_service):
        """Test user creation."""
        from app.schemas.auth import UserCreate
        
        user_data = UserCreate(
            email="newuser@example.com",
            username="newuser",
            password="TestPassword123!",
            full_name="New User"
        )
        
        user = await auth_service.create_user(db_session, user_data)
        
        assert user.email == user_data.email
        assert user.username == user_data.username
        assert user.full_name == user_data.full_name
        assert user.is_active is True
        assert user.is_verified is False
        assert user.role == UserRole.USER
        
        # Verify email service was called
        mock_email_service.send_verification_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, db_session, test_user):
        """Test successful user authentication."""
        user = await auth_service.authenticate_user(
            db_session, test_user.email, "testpassword123"
        )
        assert user is not None
        assert user.id == test_user.id

    @pytest.mark.asyncio
    async def test_authenticate_user_failure(self, db_session, test_user):
        """Test failed user authentication."""
        user = await auth_service.authenticate_user(
            db_session, test_user.email, "wrongpassword"
        )
        assert user is None