"""
Authentication and authorization service.
Handles password hashing, JWT tokens, API keys, and user management.
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List, Dict, Any
import json

from jose import jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, update as sa_update
import sqlalchemy as sa
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.auth import User, APIKey, RefreshToken, UserRole, EmailVerificationToken
from app.schemas.auth import JWTPayload, UserCreate
from app.services.email_service import create_email_service
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# Password hashing configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 30
JWT_REFRESH_TOKEN_EXPIRE_DAYS = 30


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class AuthorizationError(Exception):
    """Raised when user is not authorized for an action."""
    pass


class AuthService:
    """Authentication and authorization service."""
    
    def __init__(self):
        self.secret_key = settings.secret_key
        if len(self.secret_key) < 32:
            raise ValueError("JWT secret key must be at least 32 characters long")
        self.email_service = create_email_service()
    
    # ─── Password Management ───────────────────────────────────────────────────
    
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
    
    # ─── JWT Token Management ──────────────────────────────────────────────────
    
    def create_access_token(self, user: User, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token."""
        if expires_delta is None:
            expires_delta = timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        
        expire = datetime.now(timezone.utc) + expires_delta
        
        payload = JWTPayload(
            sub=str(user.id),
            email=user.email,
            username=user.username,
            role=user.role,
            exp=int(expire.timestamp()),
            iat=int(datetime.now(timezone.utc).timestamp()),
            jti=str(uuid.uuid4())  # Unique token ID for revocation
        )
        
        try:
            return jwt.encode(payload.model_dump(), self.secret_key, algorithm=JWT_ALGORITHM)
        except Exception as e:
            logger.error(f"JWT token creation error: {e}")
            raise AuthenticationError("Failed to create access token")
    
    def create_refresh_token(self) -> Tuple[str, str]:
        """Create a refresh token and return (token, hash)."""
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        return token, token_hash
    
    def verify_jwt_token(self, token: str) -> JWTPayload:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[JWT_ALGORITHM])
            return JWTPayload(**payload)
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.JWTError as e:
            logger.warning(f"Invalid JWT token: {e}")
            raise AuthenticationError("Invalid token")
    
    # ─── User Management ───────────────────────────────────────────────────────
    
    async def create_user(self, db: AsyncSession, user_data: UserCreate) -> User:
        """Create a new user."""
        # Check if user already exists
        existing = await db.execute(
            select(User).where(
                or_(User.email == user_data.email, User.username == user_data.username)
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("User with this email or username already exists")
        
        # Create new user
        user = User(
            email=user_data.email,
            username=user_data.username,
            full_name=user_data.full_name,
            hashed_password=self.hash_password(user_data.password),
            role=UserRole.USER,
            is_active=True,
            is_verified=False  # Require email verification in production
        )
        
        db.add(user)
        await db.flush()
        await db.refresh(user)
        
        # Create verification token for new user and send email
        try:
            token = await self.create_verification_token(db, user)
            
            # Send verification email
            frontend_url = settings.frontend_url
            verification_url = f"{frontend_url}/verify-email?token={token}"
            
            email_sent = await self.email_service.send_verification_email(
                to_email=user.email,
                verification_url=verification_url
            )
            
            if email_sent:
                logger.info(f"Created new user and sent verification email: {user.email}")
            else:
                logger.warning(f"Created new user but failed to send verification email: {user.email}")
                
        except Exception as e:
            logger.error(f"Failed to create verification token or send email for {user.email}: {e}")
            # Don't fail user creation if verification token/email fails
        
        return user
    
    async def authenticate_user(self, db: AsyncSession, email: str, password: str) -> Optional[User]:
        """Authenticate a user by email and password."""
        try:
            result = await db.execute(
                select(User).where(
                    and_(User.email == email, User.is_active == True)
                )
            )
            user = result.scalar_one_or_none()
            
            if not user or not self.verify_password(password, user.hashed_password):
                logger.warning(f"Authentication failed for user: {email}")
                return None
            
            # Update last login
            user.last_login = datetime.now(timezone.utc)
            await db.commit()
            
            logger.info(f"User authenticated successfully: {email}")
            return user
            
        except Exception as e:
            logger.error(f"Authentication error for {email}: {e}")
            return None
    
    async def get_user_by_id(self, db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
        """Get user by ID."""
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        """Get user by email."""
        result = await db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    # ─── Refresh Token Management ──────────────────────────────────────────────
    
    async def create_refresh_token_record(
        self, 
        db: AsyncSession, 
        user: User,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Tuple[str, RefreshToken]:
        """Create and store a refresh token record."""
        token, token_hash = self.create_refresh_token()
        
        refresh_token = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS),
            device_info=device_info,
            ip_address=ip_address
        )
        
        db.add(refresh_token)
        await db.flush()
        await db.refresh(refresh_token)
        
        return token, refresh_token
    
    async def verify_refresh_token(self, db: AsyncSession, token: str) -> Optional[User]:
        """Verify a refresh token and return the associated user."""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        result = await db.execute(
            select(RefreshToken).where(
                and_(
                    RefreshToken.token_hash == token_hash,
                    RefreshToken.is_active == True,
                    RefreshToken.expires_at > datetime.now(timezone.utc)
                )
            )
        )
        refresh_token = result.scalar_one_or_none()
        
        if not refresh_token:
            return None
        
        # Get the associated user
        user = await self.get_user_by_id(db, refresh_token.user_id)
        return user if user and user.is_active else None
    
    async def revoke_refresh_token(self, db: AsyncSession, token: str) -> bool:
        """Revoke a refresh token."""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        refresh_token = result.scalar_one_or_none()
        
        if refresh_token:
            refresh_token.is_active = False
            await db.commit()
            return True
        
        return False
    
    async def revoke_all_user_tokens(self, db: AsyncSession, user_id: uuid.UUID) -> int:
        """Revoke all refresh tokens for a user."""
        result = await db.execute(
            select(RefreshToken).where(
                and_(RefreshToken.user_id == user_id, RefreshToken.is_active == True)
            )
        )
        tokens = result.scalars().all()
        
        for token in tokens:
            token.is_active = False
        
        await db.commit()
        return len(tokens)
    
    # ─── API Key Management ────────────────────────────────────────────────────
    
    def generate_api_key(self) -> Tuple[str, str, str]:
        """Generate an API key and return (key, hash, prefix)."""
        # Generate a secure random key
        key = f"af_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        key_prefix = key[:12]  # First 12 chars for identification
        
        return key, key_hash, key_prefix
    
    async def create_api_key(
        self,
        db: AsyncSession,
        user: User,
        name: str,
        expires_days: Optional[int] = None,
        scopes: Optional[List[str]] = None
    ) -> Tuple[str, APIKey]:
        """Create an API key for a user."""
        key, key_hash, key_prefix = self.generate_api_key()
        
        api_key = APIKey(
            user_id=user.id,
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            expires_at=(
                datetime.now(timezone.utc) + timedelta(days=expires_days)
                if expires_days else None
            ),
            scopes=json.dumps(scopes) if scopes else None
        )
        
        db.add(api_key)
        await db.flush()
        await db.refresh(api_key)
        
        logger.info(f"Created API key '{name}' for user {user.email}")
        return key, api_key
    
    async def verify_api_key(self, db: AsyncSession, key: str) -> Optional[User]:
        """Verify an API key and return the associated user."""
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        
        result = await db.execute(
            select(APIKey).options(selectinload(APIKey.user)).where(
                and_(
                    APIKey.key_hash == key_hash,
                    APIKey.is_active == True,
                    or_(
                        APIKey.expires_at.is_(None),
                        APIKey.expires_at > datetime.now(timezone.utc)
                    )
                )
            )
        )
        api_key = result.scalar_one_or_none()
        
        if not api_key or not api_key.user or not api_key.user.is_active:
            return None
        
        # Update last used timestamp
        api_key.last_used = datetime.now(timezone.utc)
        await db.commit()
        
        return api_key.user
    
    async def revoke_api_key(self, db: AsyncSession, key_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Revoke an API key (user can only revoke their own keys)."""
        result = await db.execute(
            select(APIKey).where(
                and_(APIKey.id == key_id, APIKey.user_id == user_id)
            )
        )
        api_key = result.scalar_one_or_none()
        
        if api_key:
            api_key.is_active = False
            await db.commit()
            logger.info(f"Revoked API key {api_key.name} for user {user_id}")
            return True
        
        return False
    
    async def list_user_api_keys(self, db: AsyncSession, user_id: uuid.UUID) -> List[APIKey]:
        """List all API keys for a user."""
        result = await db.execute(
            select(APIKey).where(APIKey.user_id == user_id).order_by(APIKey.created_at.desc())
        )
        return list(result.scalars().all())
    
    # ─── Authorization ─────────────────────────────────────────────────────────
    
    def check_user_role(self, user: User, required_role: UserRole) -> bool:
        """Check if user has the required role or higher."""
        role_hierarchy = {
            UserRole.VIEWER: 0,
            UserRole.USER: 1,
            UserRole.ADMIN: 2
        }
        
        user_level = role_hierarchy.get(user.role, -1)
        required_level = role_hierarchy.get(required_role, 999)
        
        return user_level >= required_level
    
    def check_resource_access(self, user: User, resource_user_id: uuid.UUID) -> bool:
        """Check if user can access a resource owned by resource_user_id."""
        # Users can access their own resources, admins can access all
        return user.id == resource_user_id or user.role == UserRole.ADMIN
    
    def check_api_key_scopes(self, api_key: APIKey, required_scopes: List[str]) -> bool:
        """Check if API key has the required scopes."""
        if not api_key.scopes:
            return False  # No scopes means no access
        
        try:
            key_scopes = json.loads(api_key.scopes)
            return all(scope in key_scopes for scope in required_scopes)
        except (json.JSONDecodeError, TypeError):
            return False
    
    # ─── Security Utilities ────────────────────────────────────────────────────
    
    async def cleanup_expired_tokens(self, db: AsyncSession) -> int:
        """Clean up expired refresh tokens."""
        result = await db.execute(
            select(RefreshToken).where(
                RefreshToken.expires_at <= datetime.now(timezone.utc)
            )
        )
        expired_tokens = result.scalars().all()
        
        for token in expired_tokens:
            await db.delete(token)
        
        await db.commit()
        
        if expired_tokens:
            logger.info(f"Cleaned up {len(expired_tokens)} expired refresh tokens")
        
        return len(expired_tokens)
    
    # ─── Email Verification ────────────────────────────────────────────────────
    
    async def create_verification_token(self, db: AsyncSession, user: User, ip_address: Optional[str] = None) -> str:
        """Create a new email verification token for a user."""
        import secrets
        
        # Generate a secure random token
        token = secrets.token_urlsafe(32)
        token_hash = self.hash_password(token)  # Reuse password hashing for tokens
        
        # Set expiration to 24 hours from now
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        
        # Deactivate any existing tokens for this user
        await db.execute(
            sa.update(EmailVerificationToken)
            .where(EmailVerificationToken.user_id == user.id)
            .values(is_used=True)
        )
        
        # Create new verification token
        verification_token = EmailVerificationToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address
        )
        
        db.add(verification_token)
        await db.flush()
        
        logger.info(f"Created verification token for user: {user.email}")
        return token
    
    async def verify_email_with_token(self, db: AsyncSession, token: str) -> Optional[User]:
        """Verify a user's email using a verification token."""
        # Find unused, non-expired tokens
        result = await db.execute(
            select(EmailVerificationToken)
            .where(
                and_(
                    EmailVerificationToken.is_used == False,
                    EmailVerificationToken.expires_at > datetime.now(timezone.utc)
                )
            )
        )
        tokens = result.scalars().all()
        
        # Check each token's hash
        for verification_token in tokens:
            if self.verify_password(token, verification_token.token_hash):
                # Mark token as used
                verification_token.is_used = True
                verification_token.used_at = datetime.now(timezone.utc)
                
                # Get and update the user
                user_result = await db.execute(
                    select(User).where(User.id == verification_token.user_id)
                )
                user = user_result.scalar_one_or_none()
                
                if user:
                    user.is_verified = True
                    user.updated_at = datetime.now(timezone.utc)
                    
                    await db.flush()
                    logger.info(f"Email verified for user: {user.email}")
                    return user
        
        logger.warning(f"Invalid or expired verification token attempted")
        return None
    
    async def resend_verification_email(self, db: AsyncSession, email: str, ip_address: Optional[str] = None) -> bool:
        """Resend verification email to a user."""
        # Find user by email
        result = await db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            logger.warning(f"Attempted to resend verification for non-existent email: {email}")
            return False
        
        if user.is_verified:
            logger.info(f"Attempted to resend verification for already verified email: {email}")
            return False
        
        # Create new verification token
        token = await self.create_verification_token(db, user, ip_address)
        
        # Create verification URL
        frontend_url = settings.frontend_url
        verification_url = f"{frontend_url}/verify-email?token={token}"
        
        # Send verification email
        try:
            success = await self.email_service.send_verification_email(
                to_email=email,
                verification_url=verification_url
            )
            
            if success:
                logger.info(f"Verification email sent successfully to: {email}")
                return True
            else:
                logger.error(f"Failed to send verification email to: {email}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending verification email to {email}: {e}")
            return False
    
    async def get_verification_token_for_user(self, db: AsyncSession, user_id: uuid.UUID) -> Optional[str]:
        """Get the latest verification token for a user (for testing/development)."""
        result = await db.execute(
            select(EmailVerificationToken)
            .where(
                and_(
                    EmailVerificationToken.user_id == user_id,
                    EmailVerificationToken.is_used == False,
                    EmailVerificationToken.expires_at > datetime.now(timezone.utc)
                )
            )
            .order_by(EmailVerificationToken.created_at.desc())
            .limit(1)
        )
        token_record = result.scalar_one_or_none()
        
        if token_record:
            # This is a security risk - only for development!
            # In production, tokens should only be sent via email
            logger.warning("Verification token retrieved directly - this should only happen in development!")
            return "verification_token_would_be_in_email"
        
        return None
    
    def extract_user_agent(self, request_headers: Dict[str, str]) -> Optional[str]:
        """Extract user agent from request headers."""
        return request_headers.get('user-agent', None)
    
    def extract_ip_address(self, request_headers: Dict[str, str]) -> Optional[str]:
        """Extract IP address from request headers (considering proxies)."""
        # Check for forwarded headers first (common in production setups)
        forwarded_for = request_headers.get('x-forwarded-for', None)
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request_headers.get('x-real-ip', None)
        if real_ip:
            return real_ip
        
        # Fallback to remote address
        return request_headers.get('remote-addr', None)


# Global auth service instance
auth_service = AuthService()