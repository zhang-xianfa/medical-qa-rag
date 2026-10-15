from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from config.settings import Settings


class Base(DeclarativeBase):
    pass


_engine = None
_async_session_local = None


def _get_settings():
    return Settings()


def _get_engine():
    global _engine
    if _engine is None:
        s = _get_settings()
        _engine = create_async_engine(
            s.DATABASE_URL,
            pool_size=20,
            max_overflow=10,
            echo=False,
        )
    return _engine


def _get_async_session_local():
    global _async_session_local
    if _async_session_local is None:
        _async_session_local = async_sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_local


async def get_db():
    async with _get_async_session_local()() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def check_db_connection() -> bool:
    try:
        engine = _get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
