"""All-sales list: completed invoices and register sales, without double-counting."""

import pytest

from app import models as m
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_sales_made_lists_completed_sales_once(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    tenant_id = seed["t1"].id
    party_id = seed["party1"].id
    admin_id = seed["admin1"].id

    posted = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number="INV-MADE-1",
        customer_id=party_id,
        status="posted",
        subtotal=10,
        tax_amount=0,
        total_amount=10,
        paid_amount=10,
    )
    db_session.add(posted)
    await db_session.flush()
    register = m.Transaction(
        tenant_id=tenant_id,
        tx_type="pos_sale",
        reference="POS-MADE-1",
        subtotal=4,
        tax=0,
        total=4,
        status="completed",
        payload={"customer_name": "Walk-in counter", "cashier_user_id": admin_id},
    )
    linked = m.Transaction(
        tenant_id=tenant_id,
        tx_type="pos_sale",
        reference="POS-LINKED-1",
        party_id=party_id,
        subtotal=10,
        tax=0,
        total=10,
        status="completed",
        payload={"sales_invoice_id": posted.id, "customer_name": "Alpha Customer", "cashier_user_id": admin_id},
    )
    draft = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number="INV-DRAFT-SKIP",
        customer_id=party_id,
        status="draft",
        subtotal=3,
        tax_amount=0,
        total_amount=3,
    )
    db_session.add_all([register, linked, draft])
    await db_session.commit()

    resp = await ac.get("/api/v1/sales/made", headers=headers)
    assert resp.status_code == 200, resp.text
    rows = resp.json()["data"]
    numbers = {row["number"] for row in rows}
    assert "INV-MADE-1" in numbers
    assert "POS-MADE-1" in numbers
    assert "POS-LINKED-1" not in numbers
    assert "INV-DRAFT-SKIP" not in numbers
    invoice = next(row for row in rows if row["number"] == "INV-MADE-1")
    assert invoice["source"] == "invoice"
    assert invoice["customer"] == "Alpha Customer"
    register_row = next(row for row in rows if row["number"] == "POS-MADE-1")
    assert register_row["source"] == "register"
    assert register_row["customer"] == "Walk-in counter"
