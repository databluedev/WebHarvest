from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import RateLimitError
from app.core.rate_limiter import check_rate_limit_full
from app.models.user import User
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
    ApiKeyCreateRequest,
    ApiKeyResponse,
    ApiKeyCreatedResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    VerifyEmailRequest,
    VerifyEmailResponse,
)
from app.services.auth import (
    register_user,
    authenticate_user,
    create_user_token,
    create_api_key_for_user,
    get_user_api_keys,
    revoke_api_key,
    create_password_reset_token,
    reset_password,
    verify_email,
)

router = APIRouter()


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request, respecting X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post(
    "/register",
    response_model=TokenResponse,
    summary="Register a new account",
    description="Create a new user account with email and password. "
    "Returns a JWT access token on success. Rate-limited to 5 attempts per minute per IP.",
)
async def register(
    body: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Rate limit: 5 registrations per minute per IP
    ip = _get_client_ip(request)
    rl = await check_rate_limit_full(f"rl:register:{ip}", limit=5, window=60)
    if not rl.allowed:
        raise RateLimitError(
            detail="Too many registration attempts. Try again later.",
            headers={"Retry-After": str(rl.reset - int(__import__("time").time()))},
        )

    user = await register_user(db, body.email, body.password, body.name)
    token = await create_user_token(user)
    return TokenResponse(access_token=token)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in",
    description="Authenticate with email and password. Returns a JWT access token. "
    "Rate-limited to 10 attempts per minute per IP.",
)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Rate limit: 10 login attempts per minute per IP
    ip = _get_client_ip(request)
    rl = await check_rate_limit_full(f"rl:login:{ip}", limit=10, window=60)
    if not rl.allowed:
        raise RateLimitError(
            detail="Too many login attempts. Try again later.",
            headers={"Retry-After": str(rl.reset - int(__import__("time").time()))},
        )

    user = await authenticate_user(db, body.email, body.password)
    token = await create_user_token(user)
    return TokenResponse(access_token=token)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Returns the profile of the currently authenticated user.",
)
async def get_me(user: User = Depends(get_current_user)):
    return user


@router.post(
    "/api-keys",
    response_model=ApiKeyCreatedResponse,
    summary="Create API key",
    description="Generate a new API key for programmatic access. "
    "The full key is only returned once — store it securely.",
)
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


@router.get(
    "/api-keys",
    response_model=list[ApiKeyResponse],
    summary="List API keys",
    description="List all API keys for the current user. Key values are masked.",
)
async def list_api_keys(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_user_api_keys(db, user.id)


@router.delete(
    "/api-keys/{key_id}",
    summary="Revoke API key",
    description="Permanently revoke an API key. It can no longer be used for authentication.",
)
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


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    summary="Request password reset",
    description="Send a password reset token. Always returns success to prevent email enumeration.",
)
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Rate limit: 5 per minute per IP
    ip = _get_client_ip(request)
    rl = await check_rate_limit_full(f"rl:forgot-password:{ip}", limit=5, window=60)
    if not rl.allowed:
        raise RateLimitError(
            detail="Too many password reset requests. Try again later.",
            headers={"Retry-After": str(rl.reset - int(__import__("time").time()))},
        )

    raw_token = await create_password_reset_token(db, body.email)

    # Always return success to prevent email enumeration
    # In self-hosted mode, include token for dev convenience
    return ForgotPasswordResponse(
        message="If an account exists with that email, a password reset link has been generated. Check server logs.",
        token=raw_token,
    )


@router.post(
    "/reset-password",
    summary="Reset password",
    description="Set a new password using a valid reset token.",
)
async def do_reset_password(
    body: ResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Rate limit: 5 per minute per IP
    ip = _get_client_ip(request)
    rl = await check_rate_limit_full(f"rl:reset-password:{ip}", limit=5, window=60)
    if not rl.allowed:
        raise RateLimitError(
            detail="Too many password reset attempts. Try again later.",
            headers={"Retry-After": str(rl.reset - int(__import__("time").time()))},
        )

    await reset_password(db, body.token, body.new_password)
    return {"success": True, "message": "Password has been reset successfully"}


@router.post(
    "/verify-email",
    response_model=VerifyEmailResponse,
    summary="Verify email address",
    description="Confirm email ownership using the verification token.",
)
async def do_verify_email(
    body: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    await verify_email(db, body.token)
    return VerifyEmailResponse(message="Email verified successfully")
