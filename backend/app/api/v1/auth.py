from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
    ApiKeyCreateRequest,
    ApiKeyResponse,
    ApiKeyCreatedResponse,
)
from app.services.auth import (
    register_user,
    authenticate_user,
    create_user_token,
    create_api_key_for_user,
    get_user_api_keys,
    revoke_api_key,
)

router = APIRouter()


@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    user = await register_user(db, request.email, request.password, request.name)
    token = await create_user_token(user)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, request.email, request.password)
    token = await create_user_token(user)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return user


@router.post("/api-keys", response_model=ApiKeyCreatedResponse)
async def create_api_key(
    request: ApiKeyCreateRequest = ApiKeyCreateRequest(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    full_key, api_key = await create_api_key_for_user(db, user.id, request.name)
    return ApiKeyCreatedResponse(
        id=api_key.id,
        key_prefix=api_key.key_prefix,
        name=api_key.name,
        is_active=api_key.is_active,
        last_used_at=api_key.last_used_at,
        created_at=api_key.created_at,
        full_key=full_key,
    )


@router.get("/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_user_api_keys(db, user.id)


@router.delete("/api-keys/{key_id}")
async def delete_api_key(
    key_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from uuid import UUID

    success = await revoke_api_key(db, user.id, UUID(key_id))
    if not success:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("API key not found")
    return {"success": True, "message": "API key revoked"}
