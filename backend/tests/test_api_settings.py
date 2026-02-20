"""Integration tests for /v1/settings/llm-keys endpoints."""

import uuid
import pytest
from unittest.mock import patch

from httpx import AsyncClient


class TestSaveLLMKey:

    @pytest.mark.asyncio
    async def test_save_llm_key_success(self, client: AsyncClient, auth_headers):
        """PUT /v1/settings/llm-keys creates a new LLM key."""
        with patch("app.api.v1.settings.encrypt_value", return_value="encrypted_abc"), \
             patch("app.api.v1.settings.decrypt_value", return_value="sk-test1234567890abcdef"):

            resp = await client.put("/v1/settings/llm-keys", json={
                "provider": "openai",
                "api_key": "sk-test1234567890abcdef",
                "is_default": True,
            }, headers=auth_headers)

            assert resp.status_code == 200
            data = resp.json()
            assert data["provider"] == "openai"
            assert data["is_default"] is True
            assert "key_preview" in data
            assert data["id"] is not None

    @pytest.mark.asyncio
    async def test_save_llm_key_unauthenticated(self, client: AsyncClient):
        """PUT /v1/settings/llm-keys without auth returns 401."""
        resp = await client.put("/v1/settings/llm-keys", json={
            "provider": "openai",
            "api_key": "sk-test123",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_save_llm_key_upsert(self, client: AsyncClient, auth_headers):
        """PUT /v1/settings/llm-keys with same provider updates existing key."""
        with patch("app.api.v1.settings.encrypt_value", return_value="encrypted_abc"), \
             patch("app.api.v1.settings.decrypt_value", return_value="sk-first-key-12345678"):

            resp1 = await client.put("/v1/settings/llm-keys", json={
                "provider": "openai",
                "api_key": "sk-first-key-12345678",
            }, headers=auth_headers)
            first_id = resp1.json()["id"]

        with patch("app.api.v1.settings.encrypt_value", return_value="encrypted_def"), \
             patch("app.api.v1.settings.decrypt_value", return_value="sk-second-key-1234567"):

            resp2 = await client.put("/v1/settings/llm-keys", json={
                "provider": "openai",
                "api_key": "sk-second-key-1234567",
            }, headers=auth_headers)
            second_id = resp2.json()["id"]

        # Same provider should update, same ID
        assert first_id == second_id

    @pytest.mark.asyncio
    async def test_save_llm_key_missing_provider(self, client: AsyncClient, auth_headers):
        """PUT /v1/settings/llm-keys without provider returns 422."""
        resp = await client.put("/v1/settings/llm-keys", json={
            "api_key": "sk-test123",
        }, headers=auth_headers)
        assert resp.status_code == 422


class TestListLLMKeys:

    @pytest.mark.asyncio
    async def test_list_llm_keys_empty(self, client: AsyncClient, auth_headers):
        """GET /v1/settings/llm-keys returns empty list when no keys exist."""
        resp = await client.get("/v1/settings/llm-keys", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["keys"] == []

    @pytest.mark.asyncio
    async def test_list_llm_keys_unauthenticated(self, client: AsyncClient):
        """GET /v1/settings/llm-keys without auth returns 401."""
        resp = await client.get("/v1/settings/llm-keys")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_list_llm_keys_after_create(self, client: AsyncClient, auth_headers):
        """GET /v1/settings/llm-keys returns created keys."""
        with patch("app.api.v1.settings.encrypt_value", return_value="encrypted_abc"), \
             patch("app.api.v1.settings.decrypt_value", return_value="sk-test1234567890abcdef"):

            await client.put("/v1/settings/llm-keys", json={
                "provider": "openai",
                "api_key": "sk-test1234567890abcdef",
            }, headers=auth_headers)

        with patch("app.api.v1.settings.decrypt_value", return_value="sk-test1234567890abcdef"):
            resp = await client.get("/v1/settings/llm-keys", headers=auth_headers)

        data = resp.json()
        assert len(data["keys"]) == 1
        assert data["keys"][0]["provider"] == "openai"


class TestDeleteLLMKey:

    @pytest.mark.asyncio
    async def test_delete_llm_key(self, client: AsyncClient, auth_headers):
        """DELETE /v1/settings/llm-keys/{id} removes the key."""
        with patch("app.api.v1.settings.encrypt_value", return_value="encrypted_abc"), \
             patch("app.api.v1.settings.decrypt_value", return_value="sk-test1234567890abcdef"):

            create_resp = await client.put("/v1/settings/llm-keys", json={
                "provider": "anthropic",
                "api_key": "sk-test1234567890abcdef",
            }, headers=auth_headers)

        key_id = create_resp.json()["id"]

        resp = await client.delete(f"/v1/settings/llm-keys/{key_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_delete_llm_key_not_found(self, client: AsyncClient, auth_headers):
        """DELETE /v1/settings/llm-keys/{id} for non-existent key returns 404."""
        resp = await client.delete(f"/v1/settings/llm-keys/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_llm_key_unauthenticated(self, client: AsyncClient):
        """DELETE /v1/settings/llm-keys/{id} without auth returns 401."""
        resp = await client.delete(f"/v1/settings/llm-keys/{uuid.uuid4()}")
        assert resp.status_code == 401
