from datetime import datetime, timezone
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
)
from app.models.user import User
from app.models.api_key import ApiKey


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
