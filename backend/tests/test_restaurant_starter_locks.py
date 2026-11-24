"""Starter restaurants have the website, alerts, delivery and guest-growth tools switched off."""

from __future__ import annotations

import pytest
from sqlalchemy import update

from app import models as m
from app import restaurant_plan
from tests.conftest import auth_headers, set_tenant_industry

pytestmark = pytest.mark.asyncio


def test_rules_only_hit_starter_restaurants():
    hit = restaurant_plan.locked_feature
    assert hit("starter", "restaurant", "PUT /restaurant/alerts") == "alerts"
    assert hit("starter", "restaurant", "PUT /online-alerts") == "alerts"
    assert hit("starter", "restaurant", "PUT /restaurant/online-orders") == "website"
    assert hit("starter", "restaurant", "PUT /restaurant/booking-link") == "website"
    assert hit("starter", "restaurant", "POST /restaurant/till/momo") == "delivery"
    assert hit("starter", "restaurant", "POST /restaurant/orders/abc/dispatch") == "delivery"
    assert hit("starter", "restaurant", "POST /restaurant/gift-cards") == "guest_growth"
    assert hit("starter", "restaurant", "PUT /restaurant/happy-hours") == "guest_growth"
    assert hit("starter", "restaurant", "POST /restaurant/tips/share") == "guest_growth"
    assert hit("starter", "restaurant", "POST /restaurant/orders/abc/send") is None
    assert hit("professional", "restaurant", "PUT /restaurant/alerts") is None
    assert hit("trial", "restaurant", "PUT /restaurant/alerts") is None
    assert hit("starter", "retail", "PUT /online-alerts") is None


async def _starter(client, db_session, package):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    await db_session.execute(update(m.Tenant).where(m.Tenant.id == seed["t1"].id).values(package_code=package))
    await db_session.commit()
    return ac, await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def test_starter_is_refused_and_professional_is_not(client, db_session):
    ac, admin = await _starter(client, db_session, "starter")
    for method, url, body in (
        ("put", "/api/v1/restaurant/alerts", {"emails": ["owner@example.com"]}),
        ("put", "/api/v1/restaurant/happy-hours", {"rules": []}),
        ("post", "/api/v1/restaurant/gift-cards", {"amount": 50}),
    ):
        r = await getattr(ac, method)(url, headers=admin, json=body)
        assert r.status_code == 403, (url, r.text)
        assert r.json()["detail"]["code"] == "PACKAGE_UPGRADE_REQUIRED"
    assert (await ac.get("/api/v1/restaurant/alerts", headers=admin)).status_code == 200
    me = (await ac.get("/api/v1/me", headers=admin)).json()["data"]
    assert {x["key"] for x in me["package_locked_features"]} == {"website", "alerts", "delivery", "guest_growth"}

    ac, admin = await _starter(client, db_session, "professional")
    r = await ac.put("/api/v1/restaurant/alerts", headers=admin, json={"emails": ["owner@example.com"]})
    assert r.status_code == 200, r.text
    me = (await ac.get("/api/v1/me", headers=admin)).json()["data"]
    assert me["package_locked_features"] == []


def test_retail_starter_rules():
    hit = restaurant_plan.locked_feature
    assert hit("starter", "retail", "POST /gift-cards") == "gift_loyalty"
    assert hit("starter", "retail", "POST /customers/abc/loyalty") == "gift_loyalty"
    assert hit("starter", "retail", "POST /pos/momo") == "momo_prompts"
    assert hit("starter", "retail", "POST /pos/held") == "held_layaway"
    assert hit("starter", "wholesale", "POST /pos/layaways/abc/payments") == "held_layaway"
    assert hit("starter", "retail", "POST /pos/sales") is None
    assert hit("professional", "retail", "POST /gift-cards") is None
    assert hit("starter", "hotel", "POST /gift-cards") is None
    assert {x["key"] for x in restaurant_plan.starter_locks("starter", "retail")} == {
        "gift_loyalty",
        "momo_prompts",
        "held_layaway",
        "serials",
    }


async def test_retail_starter_blocks_gift_cards_and_serials(client, db_session):
    ac, seed = client
    await db_session.execute(update(m.Tenant).where(m.Tenant.id == seed["t1"].id).values(package_code="starter", industry="retail"))
    await db_session.commit()
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    r = await ac.post("/api/v1/gift-cards", headers=admin, json={"amount": 50})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "PACKAGE_UPGRADE_REQUIRED", r.text
    r = await ac.post("/api/v1/pos/held", headers=admin, json={})
    assert r.status_code == 403 and r.json()["detail"]["feature"] == "held_layaway", r.text
    r = await ac.post(
        "/api/v1/products", headers=admin, json={"name": "Phone X", "selling_price": 100, "tracks_serials": True}
    )
    assert r.status_code == 403 and r.json()["detail"]["feature"] == "serials", r.text
    await db_session.execute(update(m.Tenant).where(m.Tenant.id == seed["t1"].id).values(package_code="professional"))
    await db_session.commit()
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    r = await ac.post("/api/v1/products", headers=admin, json={"name": "Phone Y", "selling_price": 100, "tracks_serials": True})
    assert r.status_code in (200, 201), r.text
