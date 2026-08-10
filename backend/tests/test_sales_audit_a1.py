"""Stage 15 A1: sales-path domain audit for invoice_posted and sales_return_posted."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import models as m
from app.inventory import apply_stock_change
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_invoice_posted_audit_enriched_with_stock_tax_ar(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    super_h = await _super(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    product = seed["p1"]
    product.cost_price = 2
    product.stock_qty = 20
    product.reserved_qty = 0
    await db_session.commit()

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "A1 Audit Customer", "credit_limit": 5000},
    )
    assert cust.status_code == 200, cust.text
    customer_id = cust.json()["data"]["id"]

    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [
                {
                    "product_id": product.id,
                    "quantity": 3,
                    "unit_price": 20,
                    "tax_rate": 10,
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    invoice_id = created.json()["data"]["id"]
    invoice_number = created.json()["data"]["invoice_number"]
    # 3 × 20 = 60 + tax 6 = 66
    assert float(created.json()["data"]["total_amount"]) == pytest.approx(66)

    posted = await ac.post(f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers)
    assert posted.status_code == 200, posted.text

    listed = await ac.get(
        "/api/v1/audit-logs",
        headers=super_h,
        params={"action": "invoice_posted"},
    )
    assert listed.status_code == 200, listed.text
    row = next(r for r in listed.json()["data"] if r["entity_id"] == invoice_id)
    assert row["module"] == "sales"
    assert row["integrity_hash"]
    details = row["details"]
    assert details["invoice_number"] == invoice_number
    assert float(details["total"]) == pytest.approx(66)
    assert float(details["tax_amount"]) == pytest.approx(6)
    assert float(details["stock_qty_out"]) == pytest.approx(3)
    assert details["customer_id"] == customer_id
    assert float(details["customer_balance"]) == pytest.approx(66)
    assert int(details["line_count"]) == 1

    # journal_posted still linked to the invoice source
    journals = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.source_type == "sales_invoice",
                m.JournalEntry.source_id == invoice_id,
            )
        )
    ).scalars().all()
    assert len(journals) == 1
    je_audits = await ac.get(
        "/api/v1/audit-logs",
        headers=super_h,
        params={"action": "journal_posted"},
    )
    assert je_audits.status_code == 200
    je_row = next(
        r for r in je_audits.json()["data"] if r["entity_id"] == journals[0].id
    )
    assert je_row["details"].get("source_type") == "sales_invoice"
    assert je_row["details"].get("source_id") == invoice_id


@pytest.mark.asyncio
async def test_sales_return_posted_audit_and_journal_link(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    super_h = await _super(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    product = seed["p1"]
    product.cost_price = 1
    await apply_stock_change(
        db_session,
        tenant_id=tenant_id,
        product_id=product.id,
        quantity_delta=15,
        movement_type="stock_in",
        user_id=seed["mgr1"].id,
    )
    await db_session.commit()

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "A1 Return Audit Customer", "credit_limit": 5000},
    )
    customer_id = cust.json()["data"]["id"]

    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [
                {"product_id": product.id, "quantity": 2, "unit_price": 25, "tax_rate": 0}
            ],
        },
    )
    invoice_id = inv.json()["data"]["id"]
    assert (
        await ac.post(f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers)
    ).status_code == 200

    ret = await ac.post(
        "/api/v1/sales/returns",
        headers=headers,
        json={
            "sales_invoice_id": invoice_id,
            "reason": "damaged",
            "restock": True,
            "items": [{"product_id": product.id, "quantity": 1}],
        },
    )
    assert ret.status_code == 200, ret.text
    return_id = ret.json()["data"]["id"]
    posted = await ac.post(f"/api/v1/sales/returns/{return_id}/post", headers=headers)
    assert posted.status_code == 200, posted.text
    credit_note = posted.json()["data"]["credit_note_number"]
    assert credit_note

    listed = await ac.get(
        "/api/v1/audit-logs",
        headers=super_h,
        params={"action": "sales_return_posted"},
    )
    assert listed.status_code == 200, listed.text
    row = next(r for r in listed.json()["data"] if r["entity_id"] == return_id)
    assert row["module"] == "sales"
    assert row["integrity_hash"]
    details = row["details"]
    assert details["sales_invoice_id"] == invoice_id
    assert details["credit_note_number"] == credit_note
    assert details["restock"] is True
    assert float(details["restock_qty"]) == pytest.approx(1)
    assert float(details["total"]) == pytest.approx(25)
    assert details["customer_id"] == customer_id

    journals = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.source_type == "sales_return",
                m.JournalEntry.source_id == return_id,
            )
        )
    ).scalars().all()
    assert len(journals) == 1
    je_audits = await ac.get(
        "/api/v1/audit-logs",
        headers=super_h,
        params={"action": "journal_posted"},
    )
    je_row = next(
        r for r in je_audits.json()["data"] if r["entity_id"] == journals[0].id
    )
    assert je_row["details"].get("source_type") == "sales_return"
    assert je_row["details"].get("source_id") == return_id

    verify = await ac.get("/api/v1/audit-logs/verify", headers=super_h)
    assert verify.status_code == 200
    assert verify.json()["data"]["valid"] is True
