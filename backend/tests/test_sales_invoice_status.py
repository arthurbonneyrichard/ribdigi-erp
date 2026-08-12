"""Sales invoice sent + overdue status (BR-7.4)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest

from app import models as m
from app.sales import refresh_overdue_sales_invoices
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_email_marks_sent_and_overdue_refresh(client, db_session, seeded, monkeypatch):
    ac, seed = client
    admin = await _super(ac, seed)
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")

    cust = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": "Status Co", "email": "status@example.com"},
    )
    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={
            "customer_id": cust.json()["data"]["id"],
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 15}],
        },
    )
    iid = created.json()["data"]["id"]
    posted = await ac.post(f"/api/v1/sales/invoices/{iid}/post", headers=admin)
    assert posted.json()["data"]["status"] == "posted"

    sent = await ac.post(f"/api/v1/sales/invoices/{iid}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    assert sent.json()["data"]["status"] == "sent"

    inv = await db_session.get(m.SalesInvoice, iid)
    inv.due_date = datetime.utcnow() - timedelta(days=2)
    await db_session.commit()

    changed = await refresh_overdue_sales_invoices(db_session, seed["t1"].id)
    assert changed >= 1
    await db_session.refresh(inv)
    assert inv.status == "overdue"

    got = await ac.get(f"/api/v1/sales/invoices/{iid}", headers=admin)
    assert got.json()["data"]["status"] == "overdue"
    assert got.json()["data"]["days_overdue"] >= 1
    assert got.json()["data"]["can_print"] is True
    assert got.json()["data"]["can_email"] is True

    # Pay in full clears overdue
    pay = await ac.post(
        "/api/v1/sales/payments",
        headers=admin,
        json={
            "customer_id": cust.json()["data"]["id"],
            "sales_invoice_id": iid,
            "amount": float(got.json()["data"]["total_amount"]),
            "payment_method": "cash",
        },
    )
    assert pay.status_code == 200, pay.text
    final = await ac.get(f"/api/v1/sales/invoices/{iid}", headers=admin)
    assert final.json()["data"]["status"] == "paid"
