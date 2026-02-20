import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, BadRequestError
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    generate_api_key,
    hash_api_key,
    generate_reset_token,
    generate_verification_token,
    hash_token,
)
from app.models.user import User
from app.models.api_key import ApiKey
from app.models.password_reset_token import PasswordResetToken
from app.models.email_verification_token import EmailVerificationToken

logger = logging.getLogger(__name__)


async def register_user(db: AsyncSession, email: str, password: str, name: str | None = None) -> User:
    # Check if user exists
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        raise BadRequestError("Email already registered")

    user = User(
        email=email,
        password_hash=hash_password(password),
        name=name,
    )
    db.add(user)
    await db.flush()

    # Create email verification token
    raw_token = await create_verification_token(db, user.id)
    logger.info(f"[EMAIL VERIFY] User {email} — verification token: {raw_token}")

    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise AuthenticationError("Invalid email or password")
    return user


async def create_user_token(user: User) -> str:
    return create_access_token({"sub": str(user.id), "email": user.email})


async def create_api_key_for_user(
    db: AsyncSession, user_id: UUID, name: str | None = None
) -> tuple[str, ApiKey]:
    full_key, key_hash, key_prefix = generate_api_key()
    api_key = ApiKey(
        user_id=user_id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=name,
    )
    db.add(api_key)
    await db.flush()
    return full_key, api_key


async def get_user_by_api_key(db: AsyncSession, api_key: str) -> User | None:
    key_hash = hash_api_key(api_key)
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active == True)
    )
    api_key_obj = result.scalar_one_or_none()
    if not api_key_obj:
        return None

    # Update last used
    api_key_obj.last_used_at = datetime.now(timezone.utc)

    # Get user
    result = await db.execute(select(User).where(User.id == api_key_obj.user_id))
    return result.scalar_one_or_none()


async def get_user_api_keys(db: AsyncSession, user_id: UUID) -> list[ApiKey]:
    result = await db.execute(
        select(ApiKey).where(ApiKey.user_id == user_id).order_by(ApiKey.created_at.desc())
    )
    return list(result.scalars().all())


async def revoke_api_key(db: AsyncSession, user_id: UUID, key_id: UUID) -> bool:
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user_id)
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        return False
    api_key.is_active = False
    return True


# ── Password Reset ────────────────────────────────────────────

async def create_password_reset_token(db: AsyncSession, email: str) -> str | None:
    """Create a password reset token. Returns raw token or None if user not found."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        return None

    raw_token, token_hash_val = generate_reset_token()
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash_val,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(reset_token)
    await db.flush()

    logger.info(f"[PASSWORD RESET] User {email} — reset token: {raw_token}")
    return raw_token


async def reset_password(db: AsyncSession, token: str, new_password: str) -> bool:
    """Validate reset token and update password. Returns True on success."""
    token_hash_val = hash_token(token)
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash_val,
            PasswordResetToken.used == False,
            PasswordResetToken.expires_at > datetime.now(timezone.utc),
        )
    )
    reset_token = result.scalar_one_or_none()
    if not reset_token:
        raise BadRequestError("Invalid or expired reset token")

    # Update password
    user_result = await db.execute(select(User).where(User.id == reset_token.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise BadRequestError("User not found")

    user.password_hash = hash_password(new_password)
    reset_token.used = True
    await db.flush()
    return True


# ── Email Verification ────────────────────────────────────────

async def create_verification_token(db: AsyncSession, user_id: UUID) -> str:
    """Create an email verification token. Returns raw token."""
    raw_token, token_hash_val = generate_verification_token()
    verification_token = EmailVerificationToken(
        user_id=user_id,
        token_hash=token_hash_val,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(verification_token)
    await db.flush()
    return raw_token


async def verify_email(db: AsyncSession, token: str) -> bool:
    """Validate verification token and mark user as verified. Returns True on success."""
    token_hash_val = hash_token(token)
    result = await db.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_hash_val,
            EmailVerificationToken.used == False,
            EmailVerificationToken.expires_at > datetime.now(timezone.utc),
        )
    )
    verification_token = result.scalar_one_or_none()
    if not verification_token:
        raise BadRequestError("Invalid or expired verification token")

    # Mark user as verified
    user_result = await db.execute(select(User).where(User.id == verification_token.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise BadRequestError("User not found")

    user.is_verified = True
    verification_token.used = True
    await db.flush()
    return True
