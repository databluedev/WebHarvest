import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError
from app.core.security import decrypt_value
from app.models.llm_key import LLMKey

logger = logging.getLogger(__name__)

# Supported providers and their LiteLLM model prefixes
PROVIDER_PREFIXES = {
    "openai": "",  # OpenAI models don't need a prefix in LiteLLM
    "anthropic": "anthropic/",
    "groq": "groq/",
    "together": "together_ai/",
    "mistral": "mistral/",
    "cohere": "cohere/",
    "deepseek": "deepseek/",
    "fireworks": "fireworks_ai/",
    "openrouter": "openrouter/",
    "ollama": "ollama/",
}

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-20250514",
    "groq": "llama-3.1-70b-versatile",
    "together": "meta-llama/Llama-3.1-70B-Instruct-Turbo",
    "mistral": "mistral-large-latest",
    "deepseek": "deepseek-chat",
    "openrouter": "google/gemma-2-9b-it:free",
    "fireworks": "accounts/fireworks/models/llama-v3p1-70b-instruct",
    "cohere": "command-r-plus",
}


async def extract_with_llm(
    db: AsyncSession,
    user_id: UUID,
    content: str,
    prompt: str | None = None,
    schema: dict[str, Any] | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    """
    Extract structured data from content using the user's BYOK LLM key.
    Uses LiteLLM for universal provider support.
    """
    import litellm

    # Get user's LLM key
    llm_key = await _get_user_llm_key(db, user_id, provider)
    if not llm_key:
        raise BadRequestError(
            "No LLM API key configured. Add one in Settings → LLM Keys."
        )

    # Decrypt the API key
    api_key = decrypt_value(llm_key.encrypted_key)

    # Build the model string for LiteLLM
    prefix = PROVIDER_PREFIXES.get(llm_key.provider, "")
    model_name = llm_key.model or DEFAULT_MODELS.get(llm_key.provider, "gpt-4o-mini")
    model = f"{prefix}{model_name}"

    # Build the extraction prompt
    system_prompt = "You are a precise data extraction assistant. Extract structured data from the provided content."

    if schema:
        system_prompt += f"\n\nReturn a JSON object matching this schema:\n```json\n{json.dumps(schema, indent=2)}\n```"
        system_prompt += "\n\nReturn ONLY valid JSON, no markdown formatting or explanation."

    user_prompt = ""
    if prompt:
        user_prompt = f"Instruction: {prompt}\n\n"
    user_prompt += f"Content to extract from:\n\n{content}"

    # Truncate content to avoid token limits (keep ~8000 words)
    words = user_prompt.split()
    if len(words) > 8000:
        user_prompt = " ".join(words[:8000]) + "\n\n[Content truncated...]"

    try:
        response = await litellm.acompletion(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            api_key=api_key,
            response_format={"type": "json_object"} if schema else None,
            temperature=0.1,
            max_tokens=4096,
        )

        result_text = response.choices[0].message.content

        # Try to parse as JSON
        try:
            return json.loads(result_text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            if "```" in result_text:
                json_match = result_text.split("```")[1]
                if json_match.startswith("json"):
                    json_match = json_match[4:]
                return json.loads(json_match.strip())
            return {"raw_response": result_text}

    except Exception as e:
        logger.error(f"LLM extraction failed: {e}")
        raise BadRequestError(f"LLM extraction failed: {str(e)}")


async def _get_user_llm_key(
    db: AsyncSession, user_id: UUID, provider: str | None = None
) -> LLMKey | None:
    """Get the user's LLM key, preferring the specified provider or default."""
    if provider:
        result = await db.execute(
            select(LLMKey).where(
                LLMKey.user_id == user_id, LLMKey.provider == provider
            )
        )
        key = result.scalar_one_or_none()
        if key:
            return key

    # Try default key
    result = await db.execute(
        select(LLMKey).where(LLMKey.user_id == user_id, LLMKey.is_default == True)
    )
    key = result.scalar_one_or_none()
    if key:
        return key

    # Try any key
    result = await db.execute(
        select(LLMKey).where(LLMKey.user_id == user_id).limit(1)
    )
    return result.scalar_one_or_none()
