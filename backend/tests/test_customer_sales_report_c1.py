"""Customer sales report (BR-14.1)."""

from __future__ import annotations

from datetime import datetime

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_sales_by_customer_ranks_revenue_and_frequency(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    product = seed["p1"]
    tenant_id = seed["t1"].id

    stock = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={"product_id": product.id, "quantity": 100},
    )
    assert stock.status_code == 200, stock.text

    async def make_customer(name: str) -> str:
        r = await ac.post(
            "/api/v1/customers",
            headers=headers,
            json={"name": name, "credit_limit": 10000},
        )
        assert r.status_code == 200, r.text
        return r.json()["data"]["id"]

    async def post_invoice(customer_id: str, qty: int, unit_price: float) -> None:
        inv = await ac.post(
            "/api/v1/sales/invoices",
            headers=headers,
            json={
                "customer_id": customer_id,
                "items": [
                    {
                        "product_id": product.id,
                        "quantity": qty,
                        "unit_price": unit_price,
                    }
                ],
            },
        )
        assert inv.status_code == 200, inv.text
        posted = await ac.post(
            f"/api/v1/sales/invoices/{inv.json()['data']['id']}/post",
            headers=headers,
        )
        assert posted.status_code == 200, posted.text

    big = await make_customer("Big Buyer")
    small = await make_customer("Small Buyer")
    await post_invoice(big, 5, 20)  # 100
    await post_invoice(small, 1, 10)  # 10
    await post_invoice(small, 1, 15)  # 15 → small frequency 2, revenue 25

    # Walk-in POS (no party)
    db_session.add(
        m.Transaction(
            tenant_id=tenant_id,
            tx_type="pos_sale",
            reference="POS-WALK-1",
            party_id=None,
            subtotal=30,
            tax=0,
            total=30,
            status="completed",
        )
    )
    await db_session.commit()

    r = await ac.get("/api/v1/reports/sales/customers", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["customer_count"] >= 3
    names = [c["name"] for c in data["customers"]]
    assert names[0] == "Big Buyer"
    assert abs(float(data["customers"][0]["revenue"]) - 100) < 0.01
    small_row = next(c for c in data["customers"] if c["name"] == "Small Buyer")
    assert small_row["sale_count"] == 2
    assert abs(float(small_row["revenue"]) - 25) < 0.01
    walk = next(c for c in data["customers"] if c["name"] == "Walk-in")
    assert walk["customer_id"] is None
    assert abs(float(walk["pos_revenue"]) - 30) < 0.01

    limited = await ac.get("/api/v1/reports/sales/customers?limit=1", headers=headers)
    assert limited.status_code == 200
    assert len(limited.json()["data"]["customers"]) == 1
    assert limited.json()["data"]["customers"][0]["name"] == "Big Buyer"

    # Date filter excludes future-dated POS
    walk_tx = (
        await db_session.execute(
            select(m.Transaction).where(
                m.Transaction.tenant_id == tenant_id,
                m.Transaction.reference == "POS-WALK-1",
            )
        )
    ).scalar_one()
    walk_tx.created_at = datetime(2099, 1, 1)
    await db_session.commit()

    filtered = await ac.get(
        "/api/v1/reports/sales/customers?to_date=2030-01-01",
        headers=headers,
    )
    assert filtered.status_code == 200
    assert not any(c["name"] == "Walk-in" for c in filtered.json()["data"]["customers"])


def test_flatten_customers_export():
    from app.report_export import EXPORTABLE, flatten_report

    assert "sales_customers" in EXPORTABLE
    rows, lines, title = flatten_report(
        "sales_customers",
        {
            "total_revenue": 100,
            "customers": [
                {
                    "name": "Acme",
                    "sale_count": 2,
                    "revenue": 100,
                    "avg_ticket": 50,
                }
            ],
        },
    )
    assert title == "Sales by Customer"
    assert rows[0]["name"] == "Acme"
    assert any("Acme" in line for line in lines)
