"""A brand-new paying customer's first day, from provisioning to the books.

Every other walkthrough runs on a seeded company. These start from POST /tenants, so
they catch what only a new company hits: missing defaults, empty lists, unbalanced books.
"""

from __future__ import annotations

import pytest

from sqlalchemy import update

from app import models as m
from tests.conftest import platform_owner_headers

pytestmark = pytest.mark.asyncio

PASSWORD = "Fresh-Owner-2026!"


async def _new_company(ac, db, seed, industry: str):
    owner = await platform_owner_headers(ac, seed)
    email = f"owner@{industry}-new.example.com"
    slug = f"{industry}-new"
    made = await ac.post(
        "/api/v1/tenants",
        headers=owner,
        json={
            "company_name": f"Fresh {industry.title()} Ltd",
            "slug": slug,
            "industry": industry,
            "admin_email": email,
            "admin_password": PASSWORD,
        },
    )
    assert made.status_code == 200, made.text
    # The owner clicks the emailed verification link.
    await db.execute(update(m.User).where(m.User.email == email).values(email_verified=True))
    await db.commit()
    login = await ac.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD, "tenant_id": slug})
    assert login.status_code == 200, login.text
    body = login.json()["data"]
    tenant_id = made.json()["data"].get("tenant_id") or made.json()["data"].get("id")
    return {"Authorization": f"Bearer {body['access_token']}", "X-Tenant-ID": tenant_id}


async def _books_balance(ac, headers):
    trial = await ac.get("/api/v1/accounting/trial-balance", headers=headers)
    assert trial.status_code == 200, trial.text
    data = trial.json()["data"]
    assert abs(data["total_debit"] - data["total_credit"]) < 0.01, data
    assert data["total_debit"] > 0, "a sale must reach the ledger"
    return data


async def test_new_retail_company_sells_on_day_one(client, db_session):
    ac, seed = client
    h = await _new_company(ac, db_session, seed, "retail")

    assert (await ac.get("/api/v1/me", headers=h)).status_code == 200
    for path in ("/products", "/customers", "/suppliers", "/stores", "/warehouses", "/tax/rates",
                 "/accounting/accounts", "/expenses/categories", "/onboarding/checklist",
                 "/reports/sales/daily", "/reports/inventory/low-stock", "/notifications"):
        got = await ac.get(f"/api/v1{path}", headers=h)
        assert got.status_code == 200, f"{path}: {got.status_code} {got.text[:200]}"

    made = await ac.post(
        "/api/v1/products",
        headers=h,
        json={"name": "Rice 5kg", "selling_price": 100, "cost_price": 60, "stock_qty": 10, "reorder_level": 9},
    )
    assert made.status_code == 200, made.text
    product = made.json()["data"]

    opened = await ac.post("/api/v1/pos/sessions/open", headers=h, json={"opening_cash": 50})
    assert opened.status_code == 200, opened.text
    session = opened.json()["data"]
    session_id = session.get("session_id") or session.get("id")

    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=h,
        json={"session_id": session_id, "payment_method": "cash", "items": [{"product_id": product["id"], "quantity": 2}]},
    )
    assert sale.status_code == 200, sale.text
    total = sale.json()["data"]["total"]
    assert total >= 200

    after = (await ac.get(f"/api/v1/products/{product['id']}", headers=h)).json()["data"]
    assert after["stock_qty"] == 8
    low = (await ac.get("/api/v1/reports/inventory/low-stock", headers=h)).json()["data"]
    assert "Rice 5kg" in str(low), "a product under its reorder level must show as low"

    daily = (await ac.get("/api/v1/reports/sales/daily", headers=h)).json()["data"]
    assert daily["total_revenue"] > 0
    await _books_balance(ac, h)

    closed = await ac.post(
        f"/api/v1/pos/sessions/{session_id}/close", headers=h, json={"actual_cash": 50 + total}
    )
    assert closed.status_code == 200, closed.text
    assert abs(closed.json()["data"].get("variance", 0)) < 0.01, closed.text


async def test_new_restaurant_serves_on_day_one(client, db_session):
    ac, seed = client
    h = await _new_company(ac, db_session, seed, "restaurant")

    for path in ("/restaurant/tables", "/restaurant/kitchen", "/restaurant/orders", "/tax/rates",
                 "/accounting/accounts", "/onboarding/checklist"):
        got = await ac.get(f"/api/v1{path}", headers=h)
        assert got.status_code == 200, f"{path}: {got.status_code} {got.text[:200]}"

    retail_till = await ac.post("/api/v1/pos/sessions/open", headers=h, json={"opening_cash": 0})
    assert retail_till.status_code == 403, retail_till.text

    dish = await ac.post(
        "/api/v1/products",
        headers=h,
        json={"name": "Jollof and chicken", "selling_price": 65, "stock_qty": 20, "prep_station": "kitchen"},
    )
    assert dish.status_code == 200, dish.text
    dish_id = dish.json()["data"]["id"]

    shift = await ac.post("/api/v1/restaurant/till/shift/open", headers=h, json={"opening_cash": 100})
    assert shift.status_code == 200, shift.text

    order = await ac.post(
        "/api/v1/restaurant/orders",
        headers=h,
        json={"service_mode": "takeaway", "payment_method": "cash", "customer_name": "Ama",
              "lines": [{"product_id": dish_id, "quantity": "2"}]},
    )
    assert order.status_code == 200, order.text
    oid = order.json()["data"]["id"]
    sent = await ac.post(f"/api/v1/restaurant/orders/{oid}/send", headers=h)
    assert sent.status_code == 200, sent.text
    assert (await ac.get("/api/v1/restaurant/kitchen", headers=h)).json()["data"], "the kitchen must see the order"

    done = await ac.post(f"/api/v1/restaurant/orders/{oid}/complete", headers=h)
    assert done.status_code == 200, done.text
    await _books_balance(ac, h)


@pytest.mark.parametrize("industry", ["retail", "restaurant"])
async def test_no_read_screen_crashes_for_an_empty_company(client, db_session, industry):
    """Every screen loads its data from a GET. None may fall over on a company with no records."""
    from app.main import app

    ac, seed = client
    h = await _new_company(ac, db_session, seed, industry)
    paths = sorted(
        path if path.startswith("/api/v1") else f"/api/v1{path}"
        for path, ops in app.openapi()["paths"].items()
        if "get" in ops and "{" not in path and "metrics" not in path
    )
    assert len(paths) > 100
    crashed = []
    for path in paths:
        try:
            got = await ac.get(path, headers=h)
            if got.status_code >= 500:
                crashed.append(f"{path}: {got.status_code} {got.text[:120]}")
        except Exception as exc:  # noqa: BLE001
            crashed.append(f"{path}: {type(exc).__name__} {str(exc)[:120]}")
    assert not crashed, " | ".join(crashed)
