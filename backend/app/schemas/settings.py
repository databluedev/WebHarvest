from uuid import UUID
from datetime import datetime

from pydantic import BaseModel


class LLMKeyRequest(BaseModel):
    provider: str  # openai, anthropic, groq, together, etc.
    api_key: str
    model: str | None = None  # preferred model
    is_default: bool = False


class LLMKeyResponse(BaseModel):
    id: UUID
    provider: str
    model: str | None
    is_default: bool
    key_preview: str  # masked key like "sk-...abc123"
    created_at: datetime

    model_config = {"from_attributes": True}


class LLMKeyListResponse(BaseModel):
    keys: list[LLMKeyResponse]
