"""Sales returns summary report (BR-14.1)."""

from __future__ import annotations

from datetime import datetime

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_sales_returns_summary_by_reason_and_filters(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    product = seed["p1"]
    customer = seed["party1"]

    inv = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number="INV-SR-1",
        customer_id=customer.id,
        status="posted",
        subtotal=100,
        tax_amount=0,
        total_amount=100,
        posted_at=datetime.utcnow(),
    )
    db_session.add(inv)
    await db_session.flush()

    specs = [
        ("SR-1", "damaged", "posted", 40.0, 2.0, 0.0),
        ("SR-2", "damaged", "draft", 10.0, 1.0, 0.0),
        ("SR-3", "defective", "posted", 25.0, 1.0, 5.0),
        ("SR-4", "customer_change", "cancelled", 5.0, 1.0, 0.0),
    ]
    for number, reason, status, amount, qty, refunded in specs:
        ret = m.SalesReturn(
            tenant_id=tenant_id,
            return_number=number,
            customer_id=customer.id,
            sales_invoice_id=inv.id,
            status=status,
            reason=reason,
            restock=True,
            subtotal=amount,
            tax_amount=0,
            total_amount=amount,
            refunded_amount=refunded,
            settlement_method="adjust" if status == "posted" else None,
            credit_note_number=f"CN-{number}" if status == "posted" else None,
            posted_at=datetime.utcnow() if status == "posted" else None,
        )
        db_session.add(ret)
        await db_session.flush()
        db_session.add(
            m.SalesReturnItem(
                tenant_id=tenant_id,
                sales_return_id=ret.id,
                product_id=product.id,
                quantity=qty,
                unit_price=10,
                tax_rate=0,
                line_total=amount,
            )
        )
    await db_session.commit()

    r = await ac.get("/api/v1/reports/sales/returns", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["return_count"] == 4
    assert abs(float(data["total_amount"]) - 80) < 0.01
    assert abs(float(data["posted_amount"]) - 65) < 0.01
    assert abs(float(data["refunded_amount"]) - 5) < 0.01
    damaged = next(x for x in data["by_reason"] if x["reason"] == "damaged")
    assert damaged["return_count"] == 2
    assert abs(float(damaged["total_amount"]) - 50) < 0.01
    assert abs(float(damaged["quantity"]) - 3) < 0.01
    assert data["by_status"].get("posted") == 2
    assert data["by_status"].get("draft") == 1
    assert data["by_customer"][0]["name"] == customer.name

    only_damaged = await ac.get(
        "/api/v1/reports/sales/returns?reason=damaged",
        headers=headers,
    )
    assert only_damaged.status_code == 200
    assert only_damaged.json()["data"]["return_count"] == 2
    assert all(x["reason"] == "damaged" for x in only_damaged.json()["data"]["returns"])

    only_posted = await ac.get(
        "/api/v1/reports/sales/returns?status=posted",
        headers=headers,
    )
    assert only_posted.status_code == 200
    assert only_posted.json()["data"]["return_count"] == 2

    bad = await ac.get(
        "/api/v1/reports/sales/returns?reason=not-a-reason",
        headers=headers,
    )
    assert bad.status_code == 422


def test_flatten_sales_returns_export():
    from app.report_export import EXPORTABLE, flatten_report

    assert "sales_returns" in EXPORTABLE
    rows, lines, title = flatten_report(
        "sales_returns",
        {
            "return_count": 1,
            "returns": [
                {
                    "return_number": "SR-9",
                    "customer_name": "Acme",
                    "reason": "damaged",
                    "status": "posted",
                    "total_amount": 12,
                }
            ],
        },
    )
    assert title == "Sales Returns Summary"
    assert rows[0]["return_number"] == "SR-9"
    assert any("SR-9" in line for line in lines)
