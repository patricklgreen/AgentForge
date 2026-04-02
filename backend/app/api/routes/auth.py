"""
Authentication and user management API routes.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.auth.dependencies import (
    get_current_user,
    get_current_user_optional, 
    get_admin_user,
    get_current_verified_user,
    CurrentUser,
    VerifiedUser,
    AdminUser,
    DatabaseSession,
    log_security_event
)
from app.database import get_db
from app.models.auth import User, APIKey, UserRole
from app.schemas.auth import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserProfile,
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    TokenResponse,
    PasswordChangeRequest,
    APIKeyCreate,
    APIKeyResponse,
    APIKeyCreateResponse,
    StatusResponse,
    RoleUpdateRequest,
    EmailVerificationRequest,
    EmailVerificationConfirm,
    EmailVerificationResponse
)
from app.services.auth import auth_service, AuthenticationError
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])


# ─── User Registration and Login ───────────────────────────────────────────────

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    request: Request,
    db: DatabaseSession
) -> User:
    """Register a new user account."""
    try:
        user = await auth_service.create_user(db, user_data)
        await db.commit()
        
        await log_security_event(
            request, user, "user_registered", 
            {"email": user.email, "username": user.username}
        )
        
        return user
        
    except ValueError as e:
        await log_security_event(
            request, None, "registration_failed", 
            {"email": user_data.email, "error": str(e)}, 
            severity="warning"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=LoginResponse)
async def login_user(
    credentials: LoginRequest,
    request: Request,
    response: Response,
    db: DatabaseSession
) -> LoginResponse:
    """Authenticate user and return access/refresh tokens."""
    user = await auth_service.authenticate_user(db, credentials.email, credentials.password)
    
    if not user:
        await log_security_event(
            request, None, "login_failed", 
            {"email": credentials.email}, 
            severity="warning"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    if not user.is_active:
        await log_security_event(
            request, user, "login_failed_inactive", 
            {"reason": "account_inactive"}, 
            severity="warning"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive"
        )
    
    # Create tokens
    access_token = auth_service.create_access_token(user)
    
    device_info = request.headers.get('user-agent', None)
    ip_address = request.client.host if request.client else None
    
    refresh_token, refresh_record = await auth_service.create_refresh_token_record(
        db, user, device_info, ip_address
    )
    
    await db.commit()
    
    await log_security_event(
        request, user, "login_successful", 
        {"method": "password"}, 
        severity="info"
    )
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=30 * 60,  # 30 minutes
        user=UserResponse.model_validate(user)
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(
    refresh_data: RefreshTokenRequest,
    request: Request,
    db: DatabaseSession
) -> TokenResponse:
    """Refresh an access token using a refresh token."""
    user = await auth_service.verify_refresh_token(db, refresh_data.refresh_token)
    
    if not user:
        await log_security_event(
            request, None, "token_refresh_failed", 
            {"reason": "invalid_refresh_token"}, 
            severity="warning"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Create new access token
    access_token = auth_service.create_access_token(user)
    
    await log_security_event(
        request, user, "token_refreshed", 
        severity="info"
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=30 * 60  # 30 minutes
    )


@router.post("/logout", response_model=StatusResponse)
async def logout_user(
    refresh_data: RefreshTokenRequest,
    request: Request,
    user: CurrentUser,
    db: DatabaseSession
) -> StatusResponse:
    """Logout user by revoking their refresh token."""
    success = await auth_service.revoke_refresh_token(db, refresh_data.refresh_token)
    
    await log_security_event(
        request, user, "user_logged_out", 
        {"revoked": success}, 
        severity="info"
    )
    
    return StatusResponse(
        success=success,
        message="Successfully logged out" if success else "Token not found"
    )


@router.post("/logout-all", response_model=StatusResponse)
async def logout_all_devices(
    request: Request,
    user: CurrentUser,
    db: DatabaseSession
) -> StatusResponse:
    """Logout user from all devices by revoking all refresh tokens."""
    count = await auth_service.revoke_all_user_tokens(db, user.id)
    
    await log_security_event(
        request, user, "logout_all_devices", 
        {"tokens_revoked": count}, 
        severity="info"
    )
    
    return StatusResponse(
        success=True,
        message=f"Successfully logged out from {count} devices"
    )


# ─── User Profile Management ───────────────────────────────────────────────────

@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(
    user: CurrentUser,
    db: DatabaseSession
) -> UserProfile:
    """Get current user profile with additional statistics."""
    # Get project count
    from app.models.project import Project
    project_count_result = await db.execute(
        select(func.count(Project.id)).where(Project.user_id == user.id)
    )
    project_count = project_count_result.scalar() or 0
    
    # Get API key count
    api_key_count_result = await db.execute(
        select(func.count(APIKey.id)).where(APIKey.user_id == user.id)
    )
    api_key_count = api_key_count_result.scalar() or 0
    
    return UserProfile(
        **user.__dict__,
        project_count=project_count,
        api_key_count=api_key_count
    )


@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    user_update: UserUpdate,
    user: CurrentUser,
    db: DatabaseSession
) -> User:
    """Update current user profile."""
    update_data = user_update.model_dump(exclude_unset=True)
    
    # Check for email/username conflicts if they're being changed
    if "email" in update_data and update_data["email"] != user.email:
        existing = await auth_service.get_user_by_email(db, update_data["email"])
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use"
            )
    
    # Apply updates
    for field, value in update_data.items():
        setattr(user, field, value)
    
    user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    
    logger.info(f"User profile updated: {user.email}")
    return user


@router.post("/change-password", response_model=StatusResponse)
async def change_password(
    password_data: PasswordChangeRequest,
    request: Request,
    user: CurrentUser,
    db: DatabaseSession
) -> StatusResponse:
    """Change user password."""
    # Verify current password
    if not auth_service.verify_password(password_data.current_password, user.hashed_password):
        await log_security_event(
            request, user, "password_change_failed", 
            {"reason": "invalid_current_password"}, 
            severity="warning"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Update password
    user.hashed_password = auth_service.hash_password(password_data.new_password)
    user.updated_at = datetime.now(timezone.utc)
    
    # Revoke all existing refresh tokens for security
    await auth_service.revoke_all_user_tokens(db, user.id)
    await db.commit()
    
    await log_security_event(
        request, user, "password_changed", 
        {"tokens_revoked": True}, 
        severity="info"
    )
    
    return StatusResponse(
        success=True,
        message="Password changed successfully. Please log in again."
    )


# ─── API Key Management ────────────────────────────────────────────────────────

@router.post("/api-keys", response_model=APIKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    api_key_data: APIKeyCreate,
    user: VerifiedUser,
    db: DatabaseSession
) -> APIKeyCreateResponse:
    """Create a new API key for the authenticated user."""
    api_key, api_key_record = await auth_service.create_api_key(
        db, user, api_key_data.name, api_key_data.expires_days, api_key_data.scopes
    )
    await db.commit()
    
    logger.info(f"API key created: {api_key_data.name} for user {user.email}")
    
    return APIKeyCreateResponse(
        **api_key_record.__dict__,
        api_key=api_key,
        scopes=api_key_data.scopes
    )


@router.get("/api-keys", response_model=List[APIKeyResponse])
async def list_api_keys(
    user: CurrentUser,
    db: DatabaseSession
) -> List[APIKeyResponse]:
    """List all API keys for the authenticated user."""
    api_keys = await auth_service.list_user_api_keys(db, user.id)
    return [
        APIKeyResponse(
            **api_key.__dict__,
            scopes=api_key.scopes.split(',') if api_key.scopes else []
        )
        for api_key in api_keys
    ]


@router.delete("/api-keys/{key_id}", response_model=StatusResponse)
async def revoke_api_key(
    key_id: uuid.UUID,
    request: Request,
    user: CurrentUser,
    db: DatabaseSession
) -> StatusResponse:
    """Revoke an API key."""
    success = await auth_service.revoke_api_key(db, key_id, user.id)
    
    await log_security_event(
        request, user, "api_key_revoked", 
        {"key_id": str(key_id), "success": success}, 
        severity="info"
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    return StatusResponse(
        success=True,
        message="API key revoked successfully"
    )


# ─── Admin Routes ──────────────────────────────────────────────────────────────

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    admin: AdminUser,
    db: DatabaseSession,
    skip: int = 0,
    limit: int = 100,
) -> List[User]:
    """List all users (admin only)."""
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
    )
    return list(result.scalars().all())


@router.get("/users/{user_id}", response_model=UserProfile)
async def get_user(
    user_id: uuid.UUID,
    admin: AdminUser,
    db: DatabaseSession
) -> UserProfile:
    """Get user by ID (admin only)."""
    user = await auth_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get additional stats
    from app.models.project import Project
    project_count_result = await db.execute(
        select(func.count(Project.id)).where(Project.user_id == user.id)
    )
    project_count = project_count_result.scalar() or 0
    
    api_key_count_result = await db.execute(
        select(func.count(APIKey.id)).where(APIKey.user_id == user.id)
    )
    api_key_count = api_key_count_result.scalar() or 0
    
    return UserProfile(
        **user.__dict__,
        project_count=project_count,
        api_key_count=api_key_count
    )


@router.put("/users/{user_id}/role", response_model=StatusResponse)
async def update_user_role(
    user_id: uuid.UUID,
    role_update: RoleUpdateRequest,
    request: Request,
    admin: AdminUser,
    db: DatabaseSession
) -> StatusResponse:
    """Update user role (admin only)."""
    if role_update.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User ID mismatch"
        )
    
    user = await auth_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    old_role = user.role
    user.role = role_update.role
    user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    
    await log_security_event(
        request, admin, "user_role_updated", 
        {"target_user": user.email, "old_role": old_role, "new_role": role_update.role}, 
        severity="info"
    )
    
    return StatusResponse(
        success=True,
        message=f"User role updated to {role_update.role}"
    )


@router.put("/users/{user_id}/deactivate", response_model=StatusResponse)
async def deactivate_user(
    user_id: uuid.UUID,
    request: Request,
    admin: AdminUser,
    db: DatabaseSession
) -> StatusResponse:
    """Deactivate a user account (admin only)."""
    user = await auth_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )
    
    user.is_active = False
    user.updated_at = datetime.now(timezone.utc)
    
    # Revoke all tokens
    await auth_service.revoke_all_user_tokens(db, user.id)
    await db.commit()
    
    await log_security_event(
        request, admin, "user_deactivated", 
        {"target_user": user.email}, 
        severity="warning"
    )
    
    return StatusResponse(
        success=True,
        message="User account deactivated"
    )


# ─── Email Verification ──────────────────────────────────────────────────────

@router.post("/verify/send", response_model=StatusResponse)
async def send_verification_email(
    request_data: EmailVerificationRequest,
    request: Request,
    db: DatabaseSession
) -> StatusResponse:
    """
    Send email verification link to user.
    """
    try:
        ip_address = auth_service.extract_ip_address(dict(request.headers))
        success = await auth_service.resend_verification_email(
            db, request_data.email, ip_address
        )
        
        if success:
            await db.commit()
            return StatusResponse(
                success=True,
                message="Verification email sent (if email exists)"
            )
        else:
            # Don't reveal whether email exists for security
            return StatusResponse(
                success=True,
                message="Verification email sent (if email exists)"
            )
            
    except Exception as e:
        logger.error(f"Error sending verification email: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification email"
        )


@router.post("/verify/confirm", response_model=EmailVerificationResponse)
async def confirm_email_verification(
    verification_data: EmailVerificationConfirm,
    request: Request,
    db: DatabaseSession
) -> EmailVerificationResponse:
    """
    Confirm email verification using token from email.
    """
    try:
        user = await auth_service.verify_email_with_token(db, verification_data.token)
        
        if user:
            await db.commit()
            
            await log_security_event(
                request, user, "email_verified", 
                {"email": user.email}
            )
            
            return EmailVerificationResponse(
                message="Email verified successfully!",
                is_verified=True
            )
        else:
            await log_security_event(
                request, None, "email_verification_failed", 
                {"reason": "invalid_or_expired_token"},
                severity="warning"
            )
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification token"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirming email verification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify email"
        )


@router.get("/verify/status", response_model=dict)
async def get_verification_status(
    user: CurrentUser,
    db: DatabaseSession
) -> dict:
    """
    Get current user's email verification status.
    """
    # Check if user has any pending verification tokens
    has_pending_token = False
    if not user.is_verified:
        token = await auth_service.get_verification_token_for_user(db, user.id)
        has_pending_token = token is not None
    
    return {
        "is_verified": user.is_verified,
        "email": user.email,
        "has_pending_verification": has_pending_token
    }