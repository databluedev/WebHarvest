"""Shared pytest fixtures for the DataBlue backend test suite."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# ---------------------------------------------------------------------------
# Override settings BEFORE any app code is imported so that the module-level
# objects (engine, redis_client, etc.) never try to reach real Postgres/Redis.
# ---------------------------------------------------------------------------

import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key-32-bytes!!")

# ---------------------------------------------------------------------------
# SQLite compatibility: compile Postgres-specific types to SQLite equivalents
# MUST happen before any model imports that reference UUID / JSONB.
# ---------------------------------------------------------------------------

from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB as PG_JSONB  # noqa: E402
from sqlalchemy.ext.compiler import compiles  # noqa: E402


@compiles(PG_UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    """Render PostgreSQL UUID as CHAR(36) for SQLite."""
    return "CHAR(36)"


@compiles(PG_JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    """Render PostgreSQL JSONB as TEXT (JSON stored as string) for SQLite."""
    return "TEXT"


from app.core.database import Base, get_db  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.monitor import Monitor, MonitorCheck  # noqa: E402, F401
from app.models.llm_key import LLMKey  # noqa: E402, F401
from app.core.security import hash_password, create_access_token  # noqa: E402


# ---------------------------------------------------------------------------
# Async engine / session for tests (SQLite in-memory)
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite://"

_test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
_TestSessionLocal = async_sessionmaker(
    _test_engine, class_=AsyncSession, expire_on_commit=False
)


@event.listens_for(_test_engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable WAL mode and foreign keys for SQLite.

    Also register custom functions to emulate PostgreSQL-specific SQL that
    the application code relies on (date_trunc, etc.).
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()

    # Register a date_trunc function so that func.date_trunc('day', col) works.

    dbapi_connection.create_function(
        "date_trunc",
        2,
        lambda precision, dt_str: (
            dt_str[:10] if dt_str else None  # truncate to 'YYYY-MM-DD'
        ),
    )


# ---------------------------------------------------------------------------
# DB setup / teardown
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Yield a fresh async DB session backed by an in-memory SQLite database.

    Tables are created before and dropped after every test function so that
    tests are fully isolated.
    """

    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with _TestSessionLocal() as session:
        yield session

    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ---------------------------------------------------------------------------
# Mock Redis
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis():
    """Return an AsyncMock that behaves like a redis.asyncio.Redis client."""
    r = AsyncMock()
    r.pipeline.return_value = AsyncMock()
    r.pipeline.return_value.execute = AsyncMock(return_value=[0, True, 1, True])
    r.sadd = AsyncMock(return_value=1)
    r.sismember = AsyncMock(return_value=False)
    r.get = AsyncMock(return_value=None)
    r.set = AsyncMock(return_value=True)
    r.delete = AsyncMock(return_value=1)
    r.zremrangebyscore = AsyncMock()
    r.zadd = AsyncMock()
    r.zcard = AsyncMock(return_value=1)
    r.zpopmax = AsyncMock(return_value=[])
    r.hset = AsyncMock()
    r.hget = AsyncMock(return_value=None)
    r.rpush = AsyncMock(return_value=1)
    r.lpop = AsyncMock(return_value=None)
    r.llen = AsyncMock(return_value=0)
    r.expire = AsyncMock()
    return r


# ---------------------------------------------------------------------------
# Test user + JWT token
# ---------------------------------------------------------------------------

TEST_USER_EMAIL = "test@datablue.dev"
TEST_USER_PASSWORD = "supersecret123"
TEST_USER_NAME = "Test User"


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Insert a test user into the database and return the ORM object."""
    user = User(
        id=uuid.uuid4(),
        email=TEST_USER_EMAIL,
        password_hash=hash_password(TEST_USER_PASSWORD),
        name=TEST_USER_NAME,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def auth_token(test_user: User) -> str:
    """Return a valid JWT access token for the test user."""
    return create_access_token({"sub": str(test_user.id), "email": test_user.email})


@pytest_asyncio.fixture
async def auth_headers(auth_token: str) -> dict[str, str]:
    """Return an Authorization header dict ready for httpx requests."""
    return {"Authorization": f"Bearer {auth_token}"}


# ---------------------------------------------------------------------------
# Mock browser pool
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_browser_pool():
    """Return a mock BrowserPool that never launches a real browser."""
    pool = MagicMock()
    pool.initialize = AsyncMock()
    pool.shutdown = AsyncMock()
    # get_page returns an async context manager yielding a mock page
    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.content = AsyncMock(return_value="<html><body>test</body></html>")
    mock_page.screenshot = AsyncMock(return_value=b"\x89PNG\r\n\x1a\n")
    mock_page.close = AsyncMock()

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _get_page(**kwargs):
        yield mock_page

    pool.get_page = _get_page
    return pool


# ---------------------------------------------------------------------------
# FastAPI test client (ASGI transport via httpx)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, mock_redis):
    """Yield an httpx.AsyncClient wired to the FastAPI app.

    Dependency overrides ensure:
    - get_db  -> test SQLite session
    - rate limiter always allows
    - browser pool is mocked
    """

    # Patch rate limiter to always allow — patch at every import site
    from app.core.rate_limiter import RateLimitInfo

    async def _always_allow(*args, **kwargs):
        return RateLimitInfo(allowed=True, remaining=99, limit=100, reset=60)

    with (
        patch(
            "app.core.rate_limiter.check_rate_limit_full",
            side_effect=_always_allow,
        ),
        patch(
            "app.api.v1.scrape.check_rate_limit_full",
            side_effect=_always_allow,
        ),
        patch(
            "app.api.v1.crawl.check_rate_limit_full",
            side_effect=_always_allow,
        ),
        patch(
            "app.api.v1.search.check_rate_limit_full",
            side_effect=_always_allow,
        ),
        patch(
            "app.api.v1.map.check_rate_limit_full",
            side_effect=_always_allow,
        ),
        patch("app.core.rate_limiter.redis_client", mock_redis),
        patch("app.services.browser.browser_pool") as bp_mock,
    ):
        bp_mock.initialize = AsyncMock()
        bp_mock.shutdown = AsyncMock()

        # Import app AFTER patches are in place
        from app.main import app

        # Override database dependency
        async def _override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = _override_get_db

        # Disable lifespan (browser pool init/shutdown)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac

        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Authenticated client shortcut
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def authed_client(client: AsyncClient, auth_headers: dict[str, str]):
    """Return a tuple of (client, headers) for convenience."""
    return client, auth_headers
