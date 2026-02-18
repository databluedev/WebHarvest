from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AuthenticationError
from app.core.security import decode_access_token
from app.models.user import User
from app.services.auth import get_user_by_api_key


async def get_current_user(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Authenticate user via:
    1. API key (Bearer wh_...)
    2. JWT token (Bearer eyJ...)
    """
    if not authorization:
        raise AuthenticationError("Missing Authorization header")

    if not authorization.startswith("Bearer "):
        raise AuthenticationError("Invalid authorization format. Use: Bearer <token>")

    token = authorization[7:]  # Remove "Bearer "

    # Check if it's an API key (starts with wh_)
    if token.startswith("wh_"):
        user = await get_user_by_api_key(db, token)
        if not user:
            raise AuthenticationError("Invalid API key")
        return user

    # Otherwise treat as JWT
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise AuthenticationError("Invalid or expired token")

    from sqlalchemy import select
    from uuid import UUID

    result = await db.execute(select(User).where(User.id == UUID(payload["sub"])))
    user = result.scalar_one_or_none()
    if not user:
        raise AuthenticationError("User not found")

    return user
