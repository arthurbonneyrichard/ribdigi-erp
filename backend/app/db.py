from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncEngine, AsyncSession
from sqlalchemy.orm import Session

from app.config import settings
from app.desks import desk_urls
from app.schema_compat import install_live_schema_guard

engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
_desk_engines: dict[str, AsyncEngine] = {}
_current_desk: ContextVar[str | None] = ContextVar("ribdigi_desk", default=None)


def engine_for(desk: str | None) -> AsyncEngine:
    """The engine for a desk. A desk without its own database uses the main one."""
    url = desk_urls().get(desk or "")
    if not url:
        return engine
    if url not in _desk_engines:
        _desk_engines[url] = create_async_engine(url, pool_pre_ping=True)
    return _desk_engines[url]


def current_desk() -> str | None:
    return _current_desk.get()


def set_desk(desk: str | None) -> None:
    """Send this request's queries to a desk from here on."""
    _current_desk.set(desk)


@contextmanager
def on_desk(desk: str | None) -> Iterator[None]:
    """Run a block against one desk, then go back."""
    token = _current_desk.set(desk)
    try:
        yield
    finally:
        _current_desk.reset(token)


class DeskSession(Session):
    """Chooses the database at each query, so the 900 routes using a session need no change."""

    def get_bind(self, mapper=None, clause=None, **kw):
        return engine_for(_current_desk.get()).sync_engine


SessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession, sync_session_class=DeskSession
)
install_live_schema_guard()


async def get_db():
    async with SessionLocal() as db:
        yield db
