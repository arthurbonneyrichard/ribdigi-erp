"""Each desk can keep its data in its own database, and with none set nothing changes."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import create_async_engine

from app import db as db_mod
from app import desk_routing
from app import desks
from app import models as m
from app.config import settings


def test_every_desk_is_known():
    assert set(desks.DESKS) == {"retail", "hotel", "restaurant", "bakery", "fmcg", "gym", "hrm"}


@pytest.mark.parametrize(
    "industry,desk",
    [
        ("hotel", "hotel"),
        ("Restaurant", "restaurant"),
        ("FMCG", "fmcg"),
        ("gym", "gym"),
        ("hrm", "hrm"),
        ("bakery", "bakery"),
        ("pharmacy", "retail"),
        ("retail", "retail"),
        (None, "retail"),
        ("anything", "retail"),
    ],
)
def test_a_business_type_belongs_to_one_desk(industry, desk):
    assert desks.desk_for_industry(industry) == desk


def test_nothing_set_means_one_database(monkeypatch):
    monkeypatch.setattr(settings, "DESK_DATABASE_URLS", "")
    assert desks.separate_databases() is False
    assert db_mod.engine_for("hotel") is db_mod.engine


def test_a_mistyped_desk_stops_the_system_instead_of_mixing_data(monkeypatch):
    monkeypatch.setattr(settings, "DESK_DATABASE_URLS", json.dumps({"hotell": "sqlite+aiosqlite:///x.db"}))
    with pytest.raises(ValueError):
        desks.desk_urls()


def _empty_database(path) -> None:
    sync = create_engine(f"sqlite:///{path}")
    m.Base.metadata.create_all(sync)
    sync.dispose()


@pytest_asyncio.fixture
async def two_desks(tmp_path, monkeypatch):
    urls = {}
    for desk in ("hotel", "restaurant"):
        path = tmp_path / f"{desk}.db"
        _empty_database(path)
        urls[desk] = f"sqlite+aiosqlite:///{path}"
    main = tmp_path / "main.db"
    _empty_database(main)
    monkeypatch.setattr(settings, "DESK_DATABASE_URLS", json.dumps(urls))
    monkeypatch.setattr(db_mod, "engine", create_async_engine(f"sqlite+aiosqlite:///{main}"))
    monkeypatch.setattr(db_mod, "_desk_engines", {})
    desk_routing.forget_locations()
    yield
    desk_routing.forget_locations()
    for opened in [db_mod.engine, *db_mod._desk_engines.values()]:
        await opened.dispose()


async def _add_company(desk: str | None, slug: str) -> str:
    tenant_id = str(uuid4())
    with db_mod.on_desk(desk):
        async with db_mod.SessionLocal() as s:
            s.add(m.Tenant(id=tenant_id, slug=slug, company_name=slug.title()))
            await s.commit()
    return tenant_id


async def _slugs(desk: str | None) -> set[str]:
    with db_mod.on_desk(desk):
        async with db_mod.SessionLocal() as s:
            return set((await s.execute(select(m.Tenant.slug))).scalars().all())


@pytest.mark.asyncio
async def test_a_company_lives_only_in_its_desks_database(two_desks):
    await _add_company("hotel", "palm-court")
    await _add_company("restaurant", "chop-bar")
    assert await _slugs("hotel") == {"palm-court"}
    assert await _slugs("restaurant") == {"chop-bar"}
    assert await _slugs(None) == set()


@pytest.mark.asyncio
async def test_a_company_is_found_by_slug_or_id(two_desks):
    hotel_id = await _add_company("hotel", "palm-court")
    await _add_company("restaurant", "chop-bar")
    assert await desk_routing.locate_desk("palm-court") == "hotel"
    assert await desk_routing.locate_desk(hotel_id) == "hotel"
    assert await desk_routing.locate_desk("chop-bar") == "restaurant"
    assert await desk_routing.locate_desk("nobody") is None


@pytest.mark.asyncio
async def test_one_session_follows_the_company_it_was_sent_to(two_desks):
    await _add_company("hotel", "palm-court")
    with db_mod.on_desk(None):
        async with db_mod.SessionLocal() as s:
            await desk_routing.route_to_company("palm-court")
            rows = (await s.execute(select(m.Tenant.slug))).scalars().all()
    assert rows == ["palm-court"]


@pytest.mark.asyncio
async def test_a_signed_token_routes_the_request_and_a_forged_one_does_not(two_desks):
    import jwt  # PyJWT, the same library as app.security

    hotel_id = await _add_company("hotel", "palm-court")
    seen: list[str | None] = []

    async def app(scope, receive, send):
        seen.append(db_mod.current_desk())

    wrapped = desk_routing.DeskRoutingMiddleware(app)

    async def call(token: str):
        await wrapped({"type": "http", "headers": [(b"authorization", f"Bearer {token}".encode())]}, None, None)

    good = jwt.encode({"tenant_id": hotel_id}, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    forged = jwt.encode({"tenant_id": hotel_id}, "not-the-key", algorithm=settings.JWT_ALGORITHM)
    await call(good)
    await call(forged)
    assert seen == ["hotel", None]
    assert db_mod.current_desk() is None
