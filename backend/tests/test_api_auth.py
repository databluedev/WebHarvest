"""Integration tests for the /v1/auth endpoints."""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# POST /v1/auth/register
# ---------------------------------------------------------------------------


class TestRegister:
    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        """Registering a new user returns a JWT token."""
        resp = await client.post(
            "/v1/auth/register",
            json={
                "email": "newuser@datablue.dev",
                "password": "strongpass123",
                "name": "New User",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 20

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient, test_user):
        """Registering with an existing email returns 400."""
        resp = await client.post(
            "/v1/auth/register",
            json={
                "email": "test@datablue.dev",  # same as test_user
                "password": "anotherpass",
            },
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_register_missing_email(self, client: AsyncClient):
        """Missing email field returns 422 (validation error)."""
        resp = await client.post(
            "/v1/auth/register",
            json={
                "password": "somepass",
            },
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_missing_password(self, client: AsyncClient):
        """Missing password field returns 422."""
        resp = await client.post(
            "/v1/auth/register",
            json={
                "email": "nopass@test.com",
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /v1/auth/login
# ---------------------------------------------------------------------------


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, test_user):
        """Valid credentials return a JWT token."""
        resp = await client.post(
            "/v1/auth/login",
            json={
                "email": "test@datablue.dev",
                "password": "supersecret123",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, test_user):
        """Wrong password returns 401."""
        resp = await client.post(
            "/v1/auth/login",
            json={
                "email": "test@datablue.dev",
                "password": "wrongpassword",
            },
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Login with an email that doesn't exist returns 401."""
        resp = await client.post(
            "/v1/auth/login",
            json={
                "email": "noone@example.com",
                "password": "anypass",
            },
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /v1/auth/me
# ---------------------------------------------------------------------------


class TestGetMe:
    @pytest.mark.asyncio
    async def test_me_authenticated(self, client: AsyncClient, auth_headers):
        """Authenticated user can fetch their profile."""
        resp = await client.get("/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@datablue.dev"
        assert data["name"] == "Test User"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_me_no_auth(self, client: AsyncClient):
        """Request without Authorization header returns 401."""
        resp = await client.get("/v1/auth/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_me_invalid_token(self, client: AsyncClient):
        """A garbage token returns 401."""
        resp = await client.get(
            "/v1/auth/me",
            headers={
                "Authorization": "Bearer not.a.valid.jwt.token",
            },
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_me_malformed_auth_header(self, client: AsyncClient):
        """Authorization header without 'Bearer ' prefix returns 401."""
        resp = await client.get(
            "/v1/auth/me",
            headers={
                "Authorization": "Token sometoken",
            },
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# API key authentication flow
# ---------------------------------------------------------------------------


class TestApiKeyAuth:
    @pytest.mark.asyncio
    async def test_create_api_key(self, client: AsyncClient, auth_headers):
        """Authenticated user can create an API key."""
        resp = await client.post(
            "/v1/auth/api-keys", json={"name": "test-key"}, headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "full_key" in data
        assert data["full_key"].startswith("wh_")
        assert data["is_active"] is True
        assert data["name"] == "test-key"

    @pytest.mark.asyncio
    async def test_list_api_keys(self, client: AsyncClient, auth_headers):
        """List API keys returns an array."""
        # Create a key first
        await client.post(
            "/v1/auth/api-keys", json={"name": "listable"}, headers=auth_headers
        )

        resp = await client.get("/v1/auth/api-keys", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_authenticate_with_api_key(self, client: AsyncClient, auth_headers):
        """A created API key can be used to authenticate /v1/auth/me."""
        # Create key
        create_resp = await client.post(
            "/v1/auth/api-keys", json={"name": "auth-test"}, headers=auth_headers
        )
        full_key = create_resp.json()["full_key"]

        # Use the API key to call /me
        resp = await client.get(
            "/v1/auth/me",
            headers={
                "Authorization": f"Bearer {full_key}",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == "test@datablue.dev"

    @pytest.mark.asyncio
    async def test_revoke_api_key(self, client: AsyncClient, auth_headers):
        """A revoked API key can no longer authenticate."""
        # Create key
        create_resp = await client.post(
            "/v1/auth/api-keys", json={"name": "revoke-me"}, headers=auth_headers
        )
        key_data = create_resp.json()
        key_id = key_data["id"]
        full_key = key_data["full_key"]

        # Revoke it
        del_resp = await client.delete(
            f"/v1/auth/api-keys/{key_id}", headers=auth_headers
        )
        assert del_resp.status_code == 200

        # Try to use the revoked key
        resp = await client.get(
            "/v1/auth/me",
            headers={
                "Authorization": f"Bearer {full_key}",
            },
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_api_key(self, client: AsyncClient):
        """An invalid API key returns 401."""
        resp = await client.get(
            "/v1/auth/me",
            headers={
                "Authorization": "Bearer wh_this_is_not_a_real_key",
            },
        )
        assert resp.status_code == 401
