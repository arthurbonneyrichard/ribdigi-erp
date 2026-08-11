"""Stage 83 S1 — Store-scoped chart/slice depth for Store Managers."""

from __future__ import annotations

from datetime import datetime

import pytest

from app import models as m
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_store_manager_sales_trend_excludes_other_store(client, db_session):
    ac, seed = client
    tid = seed["t1"].id
    mgr = seed["mgr1"]
    store = m.Store(
        tenant_id=tid,
        name="Mgr Store",
        code="MGR-1",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        name="Other Store",
        code="OTH-1",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([store, other])
    await db_session.flush()
    now = datetime.utcnow()
    db_session.add_all(
        [
            m.SalesInvoice(
                tenant_id=tid,
                invoice_number="INV-CHART-MGR",
                customer_id=seed["party1"].id,
                status="posted",
                subtotal=25,
                tax_amount=0,
                total_amount=25,
                store_id=store.id,
                posted_at=now,
            ),
            m.SalesInvoice(
                tenant_id=tid,
                invoice_number="INV-CHART-OTH",
                customer_id=seed["party1"].id,
                status="posted",
                subtotal=500,
                tax_amount=0,
                total_amount=500,
                store_id=other.id,
                posted_at=now,
            ),
        ]
    )
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    trend = await ac.get("/api/v1/dashboard/sales-trend", headers=headers)
    assert trend.status_code == 200, trend.text
    data = trend.json()["data"]
    scope = data.get("store_scope") or {}
    assert scope.get("mode") == "managed_stores"
    assert store.id in (scope.get("store_ids") or [])
    daily = data.get("daily_revenue_series") or []
    today = now.strftime("%Y-%m-%d")
    today_pts = [p for p in daily if p.get("date") == today]
    assert today_pts, "expected today point in series"
    assert float(today_pts[0]["revenue"]) == 25.0

    top = await ac.get("/api/v1/dashboard/top-products", headers=headers)
    assert top.status_code == 200
    assert (top.json()["data"].get("store_scope") or {}).get("mode") == "managed_stores"


@pytest.mark.asyncio
async def test_executive_sales_trend_is_tenant_wide(client):
    ac, seed = client
    import pyotp

    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    r = await ac.get("/api/v1/dashboard/sales-trend", headers=headers)
    assert r.status_code == 200, r.text
    scope = r.json()["data"].get("store_scope") or {}
    assert scope.get("mode") == "tenant"
