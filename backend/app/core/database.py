from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

_engine_kwargs = {
    "echo": settings.DEBUG,
}

if _is_sqlite:
    # SQLite doesn't support pool_size/max_overflow with StaticPool
    from sqlalchemy.pool import StaticPool

    _engine_kwargs["poolclass"] = StaticPool
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
    _engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
    _engine_kwargs["pool_pre_ping"] = True
    _engine_kwargs["pool_recycle"] = 3600

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def create_worker_session_factory():
    """Create a fresh engine + session factory for Celery workers.

    Each Celery task runs in a new event loop, so we need a fresh engine
    that isn't tied to a previous (closed) loop.
    """
    _worker_kwargs = {"echo": False}
    if _is_sqlite:
        from sqlalchemy.pool import StaticPool

        _worker_kwargs["poolclass"] = StaticPool
        _worker_kwargs["connect_args"] = {"check_same_thread": False}
    else:
        _worker_kwargs["pool_size"] = settings.WORKER_DB_POOL_SIZE
        _worker_kwargs["max_overflow"] = 2
        _worker_kwargs["pool_pre_ping"] = True
        _worker_kwargs["pool_recycle"] = 3600
        _worker_kwargs["pool_timeout"] = 10

    worker_engine = create_async_engine(settings.DATABASE_URL, **_worker_kwargs)
    return async_sessionmaker(
        worker_engine, class_=AsyncSession, expire_on_commit=False
    ), worker_engine
