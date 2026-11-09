"""Finding which desk's database holds a company, and sending the request there."""

from __future__ import annotations

from sqlalchemy import or_, select

from app import models as m
from app.config import settings
from app.db import SessionLocal, on_desk, set_desk
from app.desks import desk_urls, separate_databases

_found: dict[str, str | None] = {}


def _places() -> list[str | None]:
    """Every database to look in: the main one, then each desk's own."""
    return [None, *desk_urls()]


async def locate_desk(tenant_ref: str) -> str | None:
    """The desk holding a company, by id or slug. None means the main database."""
    ref = str(tenant_ref or "").strip()
    if not ref or not separate_databases():
        return None
    if ref in _found:
        return _found[ref]
    for desk in _places():
        with on_desk(desk):
            async with SessionLocal() as db:
                hit = (
                    await db.execute(
                        select(m.Tenant.id).where(or_(m.Tenant.id == ref, m.Tenant.slug == ref)).limit(1)
                    )
                ).first()
        if hit:
            _found[ref] = desk
            return desk
    return None


async def route_to_company(tenant_ref: str) -> None:
    """Send the rest of this request to the company's database."""
    if separate_databases():
        set_desk(await locate_desk(tenant_ref))


async def route_by(stmt) -> None:
    """For a lookup with no company to go on, such as a hashed token: follow it to its database."""
    if not separate_databases():
        return
    for desk in _places():
        with on_desk(desk):
            async with SessionLocal() as db:
                hit = (await db.execute(stmt.limit(1))).first()
        if hit:
            set_desk(desk)
            return


async def rows_on_every_desk(db, stmt) -> list:
    """Rows from every database, for a lookup with no company to go on (staff sign-in).
    With one database it uses the request's own session."""
    if not separate_databases():
        return list((await db.execute(stmt)).all())
    out: list = []
    for desk in _places():
        with on_desk(desk):
            async with SessionLocal() as session:
                out.extend((await session.execute(stmt)).all())
    return out


async def taken_on_any_desk(stmt) -> bool:
    """For something unique across the whole system, such as a website address or a company slug."""
    if not separate_databases():
        return False
    for desk in _places():
        with on_desk(desk):
            async with SessionLocal() as db:
                if (await db.execute(stmt.limit(1))).first():
                    return True
    return False


def forget_locations() -> None:
    _found.clear()


class DeskRoutingMiddleware:
    """Reads the signed-in company from the token before any route opens the database.

    Plain ASGI, not BaseHTTPMiddleware, so the desk it sets is seen by everything inside it.
    A bad token routes nowhere: the route still refuses it.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or not separate_databases():
            await self.app(scope, receive, send)
            return
        desk = None
        tenant_id = _tenant_from_token(scope)
        if tenant_id:
            desk = await locate_desk(tenant_id)
        with on_desk(desk):
            await self.app(scope, receive, send)


def _tenant_from_token(scope) -> str | None:
    import jwt  # PyJWT, the same library as app.security

    headers = dict(scope.get("headers") or [])
    auth = headers.get(b"authorization", b"").decode("latin-1")
    if not auth.lower().startswith("bearer "):
        return None
    try:
        data = jwt.decode(auth[7:].strip(), settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    return data.get("tenant_id")
