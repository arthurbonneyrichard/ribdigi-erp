"""Every way into the system finds the right desk's database, through the real application."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app import db as db_mod
from app import models as m
from app.config import settings
from app.main import app
from app.rbac import permissions_for_role
from app.security import hash_password, hash_token
from tests.test_desk_databases import two_desks  # noqa: F401

PASSWORD = "SecurePass123!"


async def _company(desk, slug, industry, *, role="company_admin"):
    with db_mod.on_desk(desk):
        async with db_mod.SessionLocal() as s:
            tenant = m.Tenant(
                slug=slug, company_name=slug.title(), status="active", industry=industry, package_code="enterprise"
            )
            s.add(tenant)
            await s.flush()
            user = m.User(
                tenant_id=tenant.id,
                email=f"owner@{slug}.example.com",
                full_name="Owner",
                password_hash=hash_password(PASSWORD),
                role=role,
                email_verified=True,
                permissions=permissions_for_role(role),
                totp_enabled=False,
            )
            s.add(user)
            await s.commit()
            return tenant.id, user.id


async def _count(desk, model, *where) -> int:
    with db_mod.on_desk(desk):
        async with db_mod.SessionLocal() as s:
            return (await s.execute(select(func.count()).select_from(model).where(*where))).scalar_one()


@pytest_asyncio.fixture
async def desks_app(two_desks, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    app.dependency_overrides.clear()
    hotel = await _company("hotel", "palm-court", "hotel")
    restaurant = await _company("restaurant", "chop-bar", "restaurant")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, hotel, restaurant


async def _login(ac, slug):
    r = await ac.post(
        "/api/v1/auth/login",
        json={"tenant_id": slug, "email": f"owner@{slug}.example.com", "password": PASSWORD},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _bearer(data):
    return {"Authorization": f"Bearer {data['access_token']}"}


@pytest.mark.asyncio
async def test_each_company_signs_in_and_works_only_in_its_own_database(desks_app):
    ac, _hotel, _restaurant = desks_app
    h = _bearer(await _login(ac, "palm-court"))
    room = await ac.post("/api/v1/hotel/rooms", headers=h, json={"code": "101", "name": "Garden", "rate_amount": 100})
    assert room.status_code == 200, room.text
    assert await _count("hotel", m.HotelRoom) == 1
    assert await _count("restaurant", m.HotelRoom) == 0
    assert await _count(None, m.HotelRoom) == 0

    r = _bearer(await _login(ac, "chop-bar"))
    assert (await ac.get("/api/v1/me", headers=r)).json()["data"]["email"] == "owner@chop-bar.example.com"
    assert (await ac.get("/api/v1/me", headers=h)).json()["data"]["email"] == "owner@palm-court.example.com"


@pytest.mark.asyncio
async def test_a_company_cannot_sign_in_with_another_desks_password(desks_app):
    ac, _hotel, _restaurant = desks_app
    r = await ac.post(
        "/api/v1/auth/login",
        json={"tenant_id": "palm-court", "email": "owner@chop-bar.example.com", "password": PASSWORD},
    )
    assert r.status_code == 401, r.text


@pytest.mark.asyncio
async def test_an_unknown_company_is_simply_not_found(desks_app):
    ac, _hotel, _restaurant = desks_app
    r = await ac.post(
        "/api/v1/auth/login", json={"tenant_id": "nobody-here", "email": "a@example.com", "password": PASSWORD}
    )
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_a_write_is_audited_in_the_companys_own_database(desks_app):
    ac, (hotel_id, _u), _restaurant = desks_app
    h = _bearer(await _login(ac, "palm-court"))
    await ac.post("/api/v1/hotel/rooms", headers=h, json={"code": "102", "name": "Pool", "rate_amount": 100})
    assert await _count("hotel", m.AuditLog, m.AuditLog.tenant_id == hotel_id) > 0
    assert await _count(None, m.AuditLog) == 0
    assert await _count("restaurant", m.AuditLog, m.AuditLog.tenant_id == hotel_id) == 0


@pytest.mark.asyncio
async def test_a_refresh_token_finds_its_desk(desks_app):
    ac, _hotel, _restaurant = desks_app
    data = await _login(ac, "palm-court")
    r = await ac.post("/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_a_password_reset_link_finds_its_desk(desks_app):
    ac, (hotel_id, user_id), _restaurant = desks_app
    token = "reset-token-for-the-hotel-owner"
    with db_mod.on_desk("hotel"):
        async with db_mod.SessionLocal() as s:
            s.add(
                m.AuthToken(
                    tenant_id=hotel_id,
                    user_id=user_id,
                    token_hash=hash_token(token),
                    purpose="password_reset",
                    expires_at=datetime.utcnow() + timedelta(hours=1),
                )
            )
            await s.commit()
    r = await ac.post("/api/v1/auth/password-reset", json={"token": token, "new_password": "BrandNewPass456!"})
    assert r.status_code == 200, r.text
    again = await ac.post(
        "/api/v1/auth/login",
        json={"tenant_id": "palm-court", "email": "owner@palm-court.example.com", "password": "BrandNewPass456!"},
    )
    assert again.status_code == 200, again.text


@pytest.mark.asyncio
async def test_an_api_key_finds_its_desk(desks_app):
    ac, _hotel, _restaurant = desks_app
    h = _bearer(await _login(ac, "palm-court"))
    made = await ac.post("/api/v1/api-keys", headers=h, json={"name": "Channel manager", "permissions": {"hotel": ["read"]}})
    assert made.status_code == 200, made.text
    raw = made.json()["data"].get("key") or made.json()["data"].get("api_key") or made.json()["data"].get("raw_key")
    assert raw and raw.startswith("rdk_")
    await ac.post("/api/v1/hotel/rooms", headers=h, json={"code": "103", "name": "Sea", "rate_amount": 100})
    r = await ac.get("/api/v1/hotel/rooms", headers={"X-API-Key": raw})
    assert r.status_code == 200, r.text
    assert [row["code"] for row in r.json()["data"]] == ["103"]


@pytest.mark.asyncio
async def test_public_booking_pages_find_their_desk(desks_app):
    ac, _hotel, _restaurant = desks_app
    h = _bearer(await _login(ac, "palm-court"))
    saved = await ac.put(
        "/api/v1/hotel/booking-link", headers=h, json={"hostname": "palmcourt.example", "link_kind": "existing"}
    )
    assert saved.status_code == 200, saved.text
    by_slug = await ac.get("/api/v1/public/hotel-booking/palm-court")
    assert by_slug.status_code == 200, by_slug.text
    by_host = await ac.get("/api/v1/public/hotel-booking/by-host", params={"host": "palmcourt.example"})
    assert by_host.status_code == 200, by_host.text
    assert by_host.json()["data"]["slug"] == "palm-court"


@pytest.mark.asyncio
async def test_a_public_page_for_the_wrong_desk_shows_nothing(desks_app):
    ac, _hotel, _restaurant = desks_app
    assert (await ac.get("/api/v1/public/hotel-booking/chop-bar")).status_code == 404
    assert (await ac.get("/api/v1/public/restaurant-booking/palm-court")).status_code == 404


@pytest.mark.asyncio
async def test_a_website_address_cannot_be_claimed_on_two_desks(desks_app):
    ac, _hotel, _restaurant = desks_app
    h = _bearer(await _login(ac, "palm-court"))
    r = _bearer(await _login(ac, "chop-bar"))
    body = {"hostname": "shared.example", "link_kind": "existing"}
    assert (await ac.put("/api/v1/hotel/booking-link", headers=h, json=body)).status_code == 200
    clash = await ac.put("/api/v1/restaurant/booking-link", headers=r, json=body)
    assert clash.status_code == 409, clash.text


@pytest.mark.asyncio
async def test_a_new_company_is_created_on_its_own_desk(desks_app):
    ac, _hotel, _restaurant = desks_app
    await _company(None, "ribdigi-house", "retail", role="platform_owner")
    p = _bearer(await _login(ac, "ribdigi-house"))
    body = {
        "slug": "harbour-inn",
        "company_name": "Harbour Inn",
        "industry": "hotel",
        "admin_email": "owner@harbour.example.com",
        "admin_password": PASSWORD,
    }
    made = await ac.post("/api/v1/tenants", headers=p, json=body)
    assert made.status_code == 200, made.text
    assert await _count("hotel", m.Tenant, m.Tenant.slug == "harbour-inn") == 1
    assert await _count(None, m.Tenant, m.Tenant.slug == "harbour-inn") == 0
    assert await _count("hotel", m.User, m.User.email == "owner@harbour.example.com") == 1

    twice = await ac.post("/api/v1/tenants", headers=p, json={**body, "slug": "chop-bar", "industry": "hotel"})
    assert twice.status_code == 409, twice.text


@pytest.mark.asyncio
@pytest.mark.parametrize("industry", ["fmcg", "bakery", "gym", "hrm"])
async def test_each_new_industry_is_a_real_company_on_its_own_database(tmp_path, monkeypatch, industry):
    """Created, signed in, and kept to its own database, like retail, hotel and restaurant."""
    import json as _json

    from sqlalchemy.ext.asyncio import create_async_engine

    from app import desk_routing
    from tests.test_desk_databases import _empty_database

    own, main = tmp_path / "own.db", tmp_path / "main.db"
    _empty_database(own)
    _empty_database(main)
    monkeypatch.setattr(settings, "DESK_DATABASE_URLS", _json.dumps({industry: f"sqlite+aiosqlite:///{own}"}))
    monkeypatch.setattr(db_mod, "engine", create_async_engine(f"sqlite+aiosqlite:///{main}"))
    monkeypatch.setattr(db_mod, "_desk_engines", {})
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    desk_routing.forget_locations()
    app.dependency_overrides.clear()
    await _company(None, "ribdigi-house", "retail", role="platform_owner")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        p = _bearer(await _login(ac, "ribdigi-house"))
        made = await ac.post(
            "/api/v1/tenants",
            headers=p,
            json={
                "slug": f"{industry}-co",
                "company_name": f"{industry.title()} Co",
                "industry": industry,
                "admin_email": f"owner@{industry}-co.example.com",
                "admin_password": PASSWORD,
            },
        )
        assert made.status_code == 200, made.text
        assert await _count(industry, m.Tenant, m.Tenant.slug == f"{industry}-co") == 1
        assert await _count(None, m.Tenant, m.Tenant.slug == f"{industry}-co") == 0
        with db_mod.on_desk(industry):
            async with db_mod.SessionLocal() as s:
                owner = (
                    await s.execute(select(m.User).where(m.User.email == f"owner@{industry}-co.example.com"))
                ).scalar_one()
                owner.email_verified = True
                await s.commit()
        h = _bearer(await _login(ac, f"{industry}-co"))
        me = await ac.get("/api/v1/me", headers=h)
        assert me.status_code == 200, me.text
        assert me.json()["data"]["industry"] == industry
    desk_routing.forget_locations()
    for opened in [db_mod.engine, *db_mod._desk_engines.values()]:
        await opened.dispose()
