"""Async SQLAlchemy engine/session + schema bootstrap."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import settings

# Engine/sessionmaker are created lazily so importing this module (and the models
# that depend on it) never instantiates the async driver. Keeps pure-logic code
# and unit tests importable without a database or asyncpg installed.
_engine = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url, echo=False, pool_pre_ping=True
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _sessionmaker


def SessionLocal() -> AsyncSession:
    """Backwards-compatible factory: `async with SessionLocal() as session`."""
    return get_sessionmaker()()


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create the pgvector extension then all tables. Idempotent."""
    from sqlalchemy import text

    from . import models  # noqa: F401  (register mappers)

    async with get_engine().begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
