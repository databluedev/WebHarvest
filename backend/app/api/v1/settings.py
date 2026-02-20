from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.security import encrypt_value, decrypt_value
from app.models.llm_key import LLMKey
from app.models.user import User
from app.schemas.settings import LLMKeyRequest, LLMKeyResponse, LLMKeyListResponse

router = APIRouter()


def _mask_key(encrypted_key: str) -> str:
    """Show first 6 and last 4 chars of the decrypted key."""
    try:
        key = decrypt_value(encrypted_key)
        if len(key) <= 10:
            return key[:3] + "..." + key[-2:]
        return key[:6] + "..." + key[-4:]
    except Exception:
        return "***"


@router.put("/llm-keys", response_model=LLMKeyResponse)
async def save_llm_key(
    request: LLMKeyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save or update a BYOK LLM API key (encrypted at rest)."""
    # Check if key exists for this provider
    result = await db.execute(
        select(LLMKey).where(
            LLMKey.user_id == user.id, LLMKey.provider == request.provider
        )
    )
    existing = result.scalar_one_or_none()

    encrypted = encrypt_value(request.api_key)

    if existing:
        existing.encrypted_key = encrypted
        existing.model = request.model
        existing.is_default = request.is_default
        llm_key = existing
    else:
        llm_key = LLMKey(
            user_id=user.id,
            provider=request.provider,
            encrypted_key=encrypted,
            model=request.model,
            is_default=request.is_default,
        )
        db.add(llm_key)

    # If this is set as default, unset other defaults
    if request.is_default:
        other_keys = await db.execute(
            select(LLMKey).where(
                LLMKey.user_id == user.id,
                LLMKey.provider != request.provider,
                LLMKey.is_default == True,  # noqa: E712
            )
        )
        for key in other_keys.scalars().all():
            key.is_default = False

    await db.flush()

    return LLMKeyResponse(
        id=llm_key.id,
        provider=llm_key.provider,
        model=llm_key.model,
        is_default=llm_key.is_default,
        key_preview=_mask_key(llm_key.encrypted_key),
        created_at=llm_key.created_at,
    )


@router.get("/llm-keys", response_model=LLMKeyListResponse)
async def list_llm_keys(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all saved LLM API keys (masked)."""
    result = await db.execute(
        select(LLMKey).where(LLMKey.user_id == user.id).order_by(LLMKey.created_at)
    )
    keys = result.scalars().all()

    return LLMKeyListResponse(
        keys=[
            LLMKeyResponse(
                id=k.id,
                provider=k.provider,
                model=k.model,
                is_default=k.is_default,
                key_preview=_mask_key(k.encrypted_key),
                created_at=k.created_at,
            )
            for k in keys
        ]
    )


@router.delete("/llm-keys/{key_id}")
async def delete_llm_key(
    key_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a saved LLM API key."""
    from uuid import UUID

    result = await db.execute(
        select(LLMKey).where(LLMKey.id == UUID(key_id), LLMKey.user_id == user.id)
    )
    llm_key = result.scalar_one_or_none()
    if not llm_key:
        raise NotFoundError("LLM key not found")

    await db.delete(llm_key)
    return {"success": True, "message": "LLM key deleted"}
