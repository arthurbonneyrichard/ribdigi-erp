"""FMCG demand forecast: estimates, safety stock, reorder, flags and honesty."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest

from app import fmcg_forecast
from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers, set_tenant_industry

URL = "/api/v1/fmcg/forecast"


async def _admin(ac, seed, db_session):
    await set_tenant_industry(db_session, seed["t1"], "fmcg")
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _product(db_session, seed, stock, name="Milk"):
    p = m.Product(tenant_id=seed["t1"].id, name=f"{name} {uuid4().hex[:4]}", sku=f"F{uuid4().hex[:7]}", cost_price=5,
                  selling_price=9, stock_qty=stock, is_active=True, tracks_batches=False)
    db_session.add(p)
    await db_session.commit()
    return p.id


async def _history(db_session, seed, product_id, days_back_qty: dict[int, float], route_id=None, scheme_id=None):
    """Put delivered FMCG order lines on given days back (1 = yesterday)."""
    outlet = m.Party(tenant_id=seed["t1"].id, kind="customer", name=f"Shop {uuid4().hex[:4]}")
    db_session.add(outlet)
    await db_session.flush()
    for back, qty in days_back_qty.items():
        order = m.FmcgOrder(
            tenant_id=seed["t1"].id, order_number=f"H{uuid4().hex[:8]}", customer_id=outlet.id, route_id=route_id,
            status="delivered", delivered_at=datetime.combine(date.today() - timedelta(days=back), datetime.min.time()) + timedelta(hours=10),
        )
        db_session.add(order)
        await db_session.flush()
        db_session.add(m.FmcgOrderLine(tenant_id=seed["t1"].id, order_id=order.id, product_id=product_id, name="x",
                                       quantity=qty, scheme_id=scheme_id))
    await db_session.commit()


def _row(data, pid):
    return [p for p in data["products"] if p["product_id"] == pid][0]


@pytest.mark.asyncio
async def test_steady_demand_gives_the_documented_numbers(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    pid = await _product(db_session, seed, stock=100)
    await _history(db_session, seed, pid, {d: 10 for d in range(1, 91)})  # 10 a day, every day
    data = (await ac.get(f"{URL}?history_days=90&horizon_days=30", headers=h)).json()["data"]
    row = _row(data, pid)
    assert row["daily_forecast"] == 10.0 and row["days_of_cover"] == 10.0
    assert row["safety_stock"] == 0.0  # no variation, so no safety stock
    assert row["reorder_point"] == 70.0  # 10/day x 7 days lead time
    assert row["suggested_order"] == 10 * (7 + 30) - 100  # 270
    assert row["status"] == "ok" and row["confidence"] == "high"  # 100 in stock is above the reorder point of 70
    low = await _product(db_session, seed, stock=60)
    await _history(db_session, seed, low, {d: 10 for d in range(1, 91)})
    again = (await ac.get(f"{URL}?history_days=90&horizon_days=30", headers=h)).json()["data"]
    assert _row(again, low)["status"] == "stockout_risk"
    assert again["products"][0]["status"] == "stockout_risk"  # risks are listed first
    assert row["stockout_date"] == (date.today() + timedelta(days=10)).isoformat()
    assert data["meta"]["kind"] == "estimate" and "not sales" in data["meta"]["note"]
    assert data["accuracy"]["error_pct"] == 0.0


@pytest.mark.asyncio
async def test_variation_adds_safety_stock_and_policy_changes_results(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    pid = await _product(db_session, seed, stock=1000)
    qty = {d: (20 if d % 2 else 0) for d in range(1, 91)}  # 20 every other day
    await _history(db_session, seed, pid, qty)
    row = _row((await ac.get(URL, headers=h)).json()["data"], pid)
    expected_safety = round(1.65 * 10 * math.sqrt(7), 1)  # sd of 0/20 alternating = 10
    assert row["safety_stock"] == expected_safety
    await ac.put(f"{URL}/policy", headers=h, json={"lead_time_days": 14, "service_level": 99, "overstock_days": 120})
    row2 = _row((await ac.get(URL, headers=h)).json()["data"], pid)
    assert row2["safety_stock"] == round(2.33 * 10 * math.sqrt(14), 1) and row2["safety_stock"] > row["safety_stock"]
    assert (await ac.put(f"{URL}/policy", headers=h, json={"lead_time_days": 0, "service_level": 95, "overstock_days": 120})).status_code == 422
    assert (await ac.put(f"{URL}/policy", headers=h, json={"lead_time_days": 7, "service_level": 96, "overstock_days": 120})).status_code == 422


@pytest.mark.asyncio
async def test_overstock_dead_and_thin_history(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    over = await _product(db_session, seed, stock=5000)
    await _history(db_session, seed, over, {d: 5 for d in range(1, 91)})
    dead = await _product(db_session, seed, stock=40)
    thin = await _product(db_session, seed, stock=10)
    await _history(db_session, seed, thin, {3: 4, 9: 6})
    empty = await _product(db_session, seed, stock=0)
    data = (await ac.get(URL, headers=h)).json()["data"]
    assert _row(data, over)["status"] == "overstock" and _row(data, over)["suggested_order"] == 0
    assert _row(data, dead)["status"] == "dead"
    thin_row = _row(data, thin)
    assert thin_row["status"] == "no_forecast" and "daily_forecast" not in thin_row
    assert all(p["product_id"] != empty for p in data["products"])  # nothing to say about an unsold, empty product
    assert data["counts"]["overstock"] >= 1 and data["counts"]["dead"] >= 1 and data["counts"]["no_forecast"] >= 1


@pytest.mark.asyncio
async def test_on_order_returns_promo_share_and_trend(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    pid = await _product(db_session, seed, stock=50)
    # Demand doubled in the last 28 days; half the volume sold under a scheme.
    qty = {d: (20 if d <= 28 else 10) for d in range(1, 91)}
    await _history(db_session, seed, pid, qty, scheme_id=str(uuid4()))
    base = _row((await ac.get(URL, headers=h)).json()["data"], pid)
    assert base["trend_pct"] > 0 and base["promo_share_pct"] == 100.0
    assert base["daily_forecast"] > 10.0  # recent weeks pull the estimate up
    supplier = m.Party(tenant_id=seed["t1"].id, kind="supplier", name="Mill Ltd")
    db_session.add(supplier)
    await db_session.flush()
    po = m.PurchaseOrder(tenant_id=seed["t1"].id, po_number=f"PO{uuid4().hex[:6]}", supplier_id=supplier.id, status="sent")
    db_session.add(po)
    await db_session.flush()
    db_session.add(m.PurchaseOrderItem(tenant_id=seed["t1"].id, purchase_order_id=po.id, product_id=pid, quantity=100, received_qty=40))
    await db_session.commit()
    after = _row((await ac.get(URL, headers=h)).json()["data"], pid)
    assert after["on_order"] == 60
    assert after["suggested_order"] == max(0, base["suggested_order"] - 60)


@pytest.mark.asyncio
async def test_returns_reduce_demand_and_groups(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    cat = m.ProductCategory(tenant_id=seed["t1"].id, name="Dairy", code=f"D{uuid4().hex[:4]}")
    db_session.add(cat)
    await db_session.commit()
    pid = await _product(db_session, seed, stock=20)
    prod = await db_session.get(m.Product, pid)
    prod.category_id = cat.id
    route = m.FmcgRoute(tenant_id=seed["t1"].id, code=f"R{uuid4().hex[:4]}", name="East")
    db_session.add(route)
    await db_session.commit()
    await _history(db_session, seed, pid, {d: 10 for d in range(1, 61)}, route_id=route.id)
    line = (await db_session.execute(
        m.FmcgOrderLine.__table__.select().where(m.FmcgOrderLine.product_id == pid).limit(1))).first()
    db_session.add(m.FmcgOrderLine(tenant_id=seed["t1"].id, order_id=line.order_id, product_id=pid, name="y", quantity=0))
    await db_session.commit()
    data = (await ac.get(f"{URL}?history_days=60&horizon_days=30", headers=h)).json()["data"]
    assert data["by_category"][0]["category"] == "Dairy" and data["by_category"][0]["forecast_qty"] == 300.0
    assert data["by_route"][0]["route"] == "East" and data["by_route"][0]["share_pct"] == 100.0
    assert (await ac.get(f"{URL}?history_days=10", headers=h)).status_code == 422
    assert (await ac.get(f"{URL}?horizon_days=500", headers=h)).status_code == 422


def test_method_helpers():
    assert fmcg_forecast._daily_forecast([4.0] * 30) == 4.0
    series = [10.0] * 62 + [30.0] * 28  # 90 days; recent 28 days are 30
    assert round(fmcg_forecast._daily_forecast(series), 2) == round(0.6 * 30 + 0.4 * (sum(series) / 90), 2)
    assert fmcg_forecast._confidence([1.0] * 5 + [0.0] * 5) == "low"


@pytest.mark.asyncio
async def test_forecast_roles_and_tenant_isolation(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    pid = await _product(db_session, seed, stock=10)
    await _history(db_session, seed, pid, {d: 3 for d in range(1, 61)})
    for email, role, tenant, slug in (("rep@alpha.example.com", "fmcg_rep", "t1", "alpha"), ("admin@beta.example.com", "company_admin", "t2", "beta")):
        if tenant == "t2":
            await set_tenant_industry(db_session, seed["t2"], "fmcg")
        db_session.add(m.User(tenant_id=seed[tenant].id, email=email, full_name=role, password_hash=hash_password("SecurePass123!"),
                              role=role, email_verified=True, permissions=permissions_for_role(role), totp_enabled=False))
    await db_session.commit()
    rep = await auth_headers(ac, email="rep@alpha.example.com", tenant_slug="alpha")
    other = await auth_headers(ac, email="admin@beta.example.com", tenant_slug="beta")
    assert (await ac.get(URL, headers=rep)).status_code == 403
    assert (await ac.put(f"{URL}/policy", headers=rep, json={"lead_time_days": 7, "service_level": 95, "overstock_days": 120})).status_code == 403
    theirs = (await ac.get(URL, headers=other)).json()["data"]
    assert all(p["status"] == "dead" for p in theirs["products"]) and theirs["by_route"] == []  # none of alpha's sales leak across
    assert pid not in {p["product_id"] for p in theirs["products"]}
    assert (await ac.get(f"{URL}/policy", headers=other)).json()["data"]["lead_time_days"] == 7
