"""Async SQLAlchemy engine / session factory."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


def uses_pgbouncer(url: str | None = None) -> bool:
    """True when DATABASE_URL targets PgBouncer (host/port) or flag is set."""
    if bool(getattr(settings, "PGBOUNCER_TRANSACTION_MODE", False)):
        return True
    raw = (url or settings.DATABASE_URL or "").lower()
    return "pgbouncer" in raw or ":6432" in raw


def engine_kwargs_for_url(url: str | None = None) -> dict:
    """
    Build create_async_engine kwargs.

    Stage 27 P1: transaction-mode PgBouncer remaps server backends between
    transactions — asyncpg's prepared-statement cache must be disabled.
    """
    kwargs: dict = {"pool_pre_ping": True}
    if uses_pgbouncer(url):
        kwargs["connect_args"] = {"statement_cache_size": 0}
        kwargs["pool_size"] = int(getattr(settings, "DB_POOL_SIZE", 5) or 5)
        kwargs["max_overflow"] = int(getattr(settings, "DB_MAX_OVERFLOW", 5) or 5)
    return kwargs


engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs_for_url())
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db():
    async with SessionLocal() as db:
        yield db
