"""
Authentication fixtures and utilities for testing.
"""
import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient

from app.models.auth import User, UserRole, APIKey, RefreshToken
from app.services.auth import auth_service


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user (unique email so committed rows do not collide across tests)."""
    uid = uuid.uuid4().hex[:12]
    user = User(
        id=uuid.uuid4(),
        email=f"test-{uid}@example.com",
        username=f"testuser-{uid}",
        hashed_password=auth_service.hash_password("testpassword123"),
        full_name="Test User",
        role=UserRole.USER,
        is_active=True,
        is_verified=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create an admin test user."""
    uid = uuid.uuid4().hex[:12]
    user = User(
        id=uuid.uuid4(),
        email=f"admin-{uid}@example.com",
        username=f"admin-{uid}",
        hashed_password=auth_service.hash_password("adminpassword123"),
        full_name="Admin User",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def inactive_user(db_session: AsyncSession) -> User:
    """Create an inactive test user."""
    uid = uuid.uuid4().hex[:12]
    user = User(
        id=uuid.uuid4(),
        email=f"inactive-{uid}@example.com",
        username=f"inactiveuser-{uid}",
        hashed_password=auth_service.hash_password("password123"),
        role=UserRole.USER,
        is_active=False,
        is_verified=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_api_key(db_session: AsyncSession, test_user: User) -> APIKey:
    """Create a test API key."""
    key_value = "test-key-12345"
    api_key = APIKey(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Test API Key",
        key_hash=hashlib.sha256(key_value.encode()).hexdigest(),
        key_prefix="test-key",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(api_key)
    await db_session.commit()
    await db_session.refresh(api_key)
    # Store the unhashed key value for testing
    api_key._test_key_value = key_value
    return api_key


@pytest.fixture
async def test_refresh_token(db_session: AsyncSession, test_user: User) -> RefreshToken:
    """Create a test refresh token."""
    token_value = "refresh-token-12345"
    refresh_token = RefreshToken(
        id=uuid.uuid4(),
        user_id=test_user.id,
        token_hash=hashlib.sha256(token_value.encode()).hexdigest(),
        is_active=True,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(refresh_token)
    await db_session.commit()
    await db_session.refresh(refresh_token)
    # Store the unhashed token value for testing
    refresh_token._test_token_value = token_value
    return refresh_token


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    """Generate JWT auth headers for test user."""
    access_token = auth_service.create_access_token(test_user)
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def admin_headers(admin_user: User) -> dict:
    """Generate JWT auth headers for admin user."""
    access_token = auth_service.create_access_token(admin_user)
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def api_key_headers(test_api_key: APIKey) -> dict:
    """Generate API key headers for testing."""
    return {"X-API-Key": test_api_key._test_key_value}


async def create_authenticated_user(
    db_session: AsyncSession,
    email: str = "user@test.com",
    username: str = "testuser",
    password: str = "testpass123",
    role: UserRole = UserRole.USER,
    is_active: bool = True,
    is_verified: bool = True,
) -> User:
    """Helper to create a user with authentication."""
    user = User(
        id=uuid.uuid4(),
        email=email,
        username=username,
        hashed_password=auth_service.hash_password(password),
        role=role,
        is_active=is_active,
        is_verified=is_verified,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def get_jwt_headers(user: User) -> dict:
    """Get JWT headers for a user."""
    access_token = auth_service.create_access_token(user)
    return {"Authorization": f"Bearer {access_token}"}


async def login_user(client: AsyncClient, email: str, password: str) -> dict:
    """Login a user and return the response data."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password}
    )
    return response.json()