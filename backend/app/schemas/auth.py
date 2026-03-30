"""
Authentication and authorization schemas for API requests and responses.
"""
import uuid
import re
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator

from app.models.auth import UserRole


# ─── User Schemas ──────────────────────────────────────────────────────────────

class UserBase(BaseModel):
    email: str = Field(..., description="User email address")
    username: str = Field(..., min_length=3, max_length=100)
    full_name: Optional[str] = Field(None, max_length=200)

    @validator('email')
    def validate_email(cls, v):
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError('Invalid email format')
        return v


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=100)
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class UserUpdate(BaseModel):
    email: Optional[str] = None
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    full_name: Optional[str] = Field(None, max_length=200)
    is_active: Optional[bool] = None

    @validator('email')
    def validate_email(cls, v):
        if v and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError('Invalid email format')
        return v


class UserResponse(UserBase):
    id: uuid.UUID
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class UserProfile(UserResponse):
    """Extended user profile with additional information."""
    project_count: Optional[int] = None
    api_key_count: Optional[int] = None


# ─── Authentication Schemas ────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str

    @validator('email')
    def validate_email(cls, v):
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError('Invalid email format')
        return v


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class PasswordResetRequest(BaseModel):
    email: str

    @validator('email')
    def validate_email(cls, v):
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError('Invalid email format')
        return v


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=100)
    
    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)
    
    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


# ─── API Key Schemas ───────────────────────────────────────────────────────────

class APIKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    expires_days: Optional[int] = Field(None, ge=1, le=365)
    scopes: Optional[List[str]] = None


class APIKeyResponse(BaseModel):
    id: uuid.UUID
    name: str
    key_prefix: str
    is_active: bool
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    created_at: datetime
    scopes: Optional[List[str]] = None
    
    class Config:
        from_attributes = True


class APIKeyCreateResponse(APIKeyResponse):
    """Response that includes the actual API key (only returned on creation)."""
    api_key: str


# ─── JWT Claims ───────────────────────────────────────────────────────────────

class JWTPayload(BaseModel):
    """JWT token payload structure."""
    sub: str  # user_id
    email: str
    username: str
    role: UserRole
    exp: int  # expiration timestamp
    iat: int  # issued at timestamp
    jti: str  # JWT ID for token tracking


# ─── Permission and Role Management ────────────────────────────────────────────

class RoleUpdateRequest(BaseModel):
    user_id: uuid.UUID
    role: UserRole


class PermissionCheck(BaseModel):
    """For checking user permissions."""
    resource: str
    action: str
    resource_id: Optional[str] = None


# ─── Security Events ──────────────────────────────────────────────────────────

class SecurityEvent(BaseModel):
    """For logging security-related events."""
    event_type: str
    user_id: Optional[uuid.UUID] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[dict] = None
    severity: str = "info"  # info, warning, error, critical


# ─── Response Status ──────────────────────────────────────────────────────────

class StatusResponse(BaseModel):
    """Generic status response."""
    success: bool
    message: str
    details: Optional[dict] = None