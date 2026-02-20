from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=3600,
)

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
    worker_engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=settings.WORKER_DB_POOL_SIZE,
        max_overflow=2,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    return async_sessionmaker(
        worker_engine, class_=AsyncSession, expire_on_commit=False
    ), worker_engine
