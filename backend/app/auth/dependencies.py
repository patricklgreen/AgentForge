"""
Authentication dependencies for FastAPI routes.
Provides dependency injection for JWT authentication, API key authentication,
and role-based access control.
"""
import uuid
from typing import Optional, List, Annotated

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.auth import User, UserRole
from app.services.auth import auth_service, AuthenticationError, AuthorizationError
from app.schemas.auth import JWTPayload
import logging

logger = logging.getLogger(__name__)

# Security schemes
jwt_bearer = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_user_jwt(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(jwt_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> Optional[User]:
    """
    Get current user from JWT token.
    Returns None if no valid token is provided (allows for optional auth).
    """
    if not credentials or not credentials.credentials:
        return None
    
    try:
        # Verify JWT token
        payload = auth_service.verify_jwt_token(credentials.credentials)
        
        # Get user from database
        user = await auth_service.get_user_by_id(db, uuid.UUID(payload.sub))
        
        if not user or not user.is_active:
            return None
        
        return user
        
    except (AuthenticationError, ValueError) as e:
        logger.warning(f"JWT authentication failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in JWT authentication: {e}")
        return None


async def get_current_user_api_key(
    api_key: Annotated[Optional[str], Depends(api_key_header)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> Optional[User]:
    """
    Get current user from API key.
    Returns None if no valid API key is provided (allows for optional auth).
    """
    if not api_key:
        return None
    
    try:
        user = await auth_service.verify_api_key(db, api_key)
        return user if user and user.is_active else None
        
    except Exception as e:
        logger.error(f"API key authentication error: {e}")
        return None


async def get_current_user_optional(
    user_jwt: Annotated[Optional[User], Depends(get_current_user_jwt)],
    user_api_key: Annotated[Optional[User], Depends(get_current_user_api_key)]
) -> Optional[User]:
    """
    Get current user from either JWT or API key (optional authentication).
    Returns None if no valid authentication is provided.
    """
    return user_jwt or user_api_key


async def get_current_user(
    user: Annotated[Optional[User], Depends(get_current_user_optional)]
) -> User:
    """
    Get current authenticated user (required authentication).
    Raises 401 if no valid authentication is provided.
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user account"
        )
    
    return user


async def get_current_verified_user(
    user: Annotated[User, Depends(get_current_user)]
) -> User:
    """
    Get current authenticated and verified user.
    Raises 403 if user is not verified.
    """
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required"
        )
    
    return user


def require_role(required_role: UserRole):
    """
    Dependency factory for role-based access control.
    
    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(user: User = Depends(require_role(UserRole.ADMIN))):
            ...
    """
    async def role_checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if not auth_service.check_user_role(user, required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient privileges. Required role: {required_role.value}"
            )
        return user
    
    return role_checker


def require_resource_access(resource_user_id_param: str = "user_id"):
    """
    Dependency factory for resource-based access control.
    Checks if the current user can access a resource owned by another user.
    
    Args:
        resource_user_id_param: The name of the path/query parameter containing the resource owner's user ID
    
    Usage:
        @router.get("/users/{user_id}/projects")
        async def get_user_projects(
            user_id: uuid.UUID,
            user: User = Depends(require_resource_access("user_id"))
        ):
            ...
    """
    async def access_checker(
        request: Request,
        user: Annotated[User, Depends(get_current_user)]
    ) -> User:
        # Extract the resource user ID from path parameters
        resource_user_id = request.path_params.get(resource_user_id_param)
        
        if not resource_user_id:
            # If no resource user ID is found, fall back to query parameters
            resource_user_id = request.query_params.get(resource_user_id_param)
        
        if not resource_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required parameter: {resource_user_id_param}"
            )
        
        try:
            resource_user_uuid = uuid.UUID(resource_user_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid UUID format for {resource_user_id_param}"
            )
        
        if not auth_service.check_resource_access(user, resource_user_uuid):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this resource"
            )
        
        return user
    
    return access_checker


async def get_admin_user(
    user: Annotated[User, Depends(require_role(UserRole.ADMIN))]
) -> User:
    """Convenience dependency for admin-only routes."""
    return user


# ─── Project-specific dependencies ─────────────────────────────────────────────

async def get_current_user_for_project(
    project_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> User:
    """
    Check if the current user has access to a specific project.
    
    Users can access:
    - Their own projects
    - Any project if they're an admin
    """
    from app.models.project import Project
    from sqlalchemy import select
    
    # Admins have access to all projects
    if user.role == UserRole.ADMIN:
        return user
    
    # Check if the project belongs to the user
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    if project.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this project"
        )
    
    return user


# ─── Security logging ──────────────────────────────────────────────────────────

async def log_security_event(
    request: Request,
    user: Optional[User],
    event_type: str,
    details: Optional[dict] = None,
    severity: str = "info"
) -> None:
    """Log security-related events for monitoring and auditing."""
    try:
        user_agent = request.headers.get('user-agent', 'Unknown')
        ip_address = request.client.host if request.client else 'Unknown'
        
        # In production, you would send this to a security monitoring system
        logger.info(
            f"Security Event: {event_type} | "
            f"User: {user.email if user else 'Anonymous'} | "
            f"IP: {ip_address} | "
            f"User-Agent: {user_agent} | "
            f"Severity: {severity} | "
            f"Details: {details or {}}"
        )
    except Exception as e:
        logger.error(f"Failed to log security event: {e}")


# ─── Type aliases for cleaner dependency injection ─────────────────────────────

CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentUserOptional = Annotated[Optional[User], Depends(get_current_user_optional)]
VerifiedUser = Annotated[User, Depends(get_current_verified_user)]
AdminUser = Annotated[User, Depends(get_admin_user)]
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]