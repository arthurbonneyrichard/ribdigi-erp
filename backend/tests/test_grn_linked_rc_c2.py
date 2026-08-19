"""Stage 11 C2: GRN-linked reverse-charge PI posts self-assess tax only."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import models as m
from app import purchasing as purchasing_svc
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_grn_linked_rc_posts_self_assess_only(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    seed["p1"].stock_qty = 0
    await db_session.commit()

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "RC Chain Sup"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    # Net PO (tax memo only via RC on invoice): 10 @ 10 = 100
    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [
                {
                    "product_id": str(seed["p1"].id),
                    "quantity": 10,
                    "unit_price": 10,
                    "tax_rate": 0,
                }
            ],
        },
    )
    assert po.status_code == 200, po.text
    po_id = po.json()["data"]["id"]
    po_item_id = po.json()["data"]["items"][0]["id"]

    assert (
        await ac.post(f"/api/v1/purchasing/orders/{po_id}/send", headers=headers)
    ).status_code == 200

    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=headers,
        json={
            "purchase_order_id": po_id,
            "items": [
                {
                    "po_item_id": po_item_id,
                    "received_qty": 10,
                    "accepted_qty": 10,
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    grn_id = grn.json()["data"]["id"]

    balance_after_grn = float(
        (await ac.get(f"/api/v1/suppliers/{supplier_id}", headers=headers)).json()["data"][
            "balance"
        ]
    )
    assert balance_after_grn == pytest.approx(100)

    inv = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={
            "goods_receipt_id": grn_id,
            "is_reverse_charge": True,
            "items": [
                {
                    "product_id": str(seed["p1"].id),
                    "quantity": 10,
                    "unit_price": 10,
                    "tax_rate": 15,
                }
            ],
        },
    )
    assert inv.status_code == 200, inv.text
    inv_body = inv.json()["data"]
    inv_id = inv_body["id"]
    assert float(inv_body["total_amount"]) == pytest.approx(100)
    assert float(inv_body["tax_amount"]) == pytest.approx(0)
    assert float(inv_body["reverse_charge_tax"]) == pytest.approx(15)

    approved = await ac.post(
        f"/api/v1/purchasing/invoices/{inv_id}/approve", headers=headers
    )
    assert approved.status_code == 200, approved.text
    appr = approved.json()["data"]
    assert appr.get("ap_posted") is False

    # Supplier balance unchanged (GRN already owns AP)
    balance_after_approve = float(
        (await ac.get(f"/api/v1/suppliers/{supplier_id}", headers=headers)).json()["data"][
            "balance"
        ]
    )
    assert balance_after_approve == pytest.approx(balance_after_grn)

    entry = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.source_type == "purchase_invoice",
                m.JournalEntry.source_id == inv_id,
            )
        )
    ).scalar_one()
    lines = (
        await db_session.execute(
            select(m.JournalEntryLine).where(m.JournalEntryLine.journal_entry_id == entry.id)
        )
    ).scalars().all()
    by_account = {}
    for ln in lines:
        acct = (
            await db_session.execute(select(m.Account).where(m.Account.id == ln.account_id))
        ).scalar_one()
        by_account[acct.code] = (float(ln.debit), float(ln.credit))

    assert set(by_account) == {"1300", "2100"}
    assert by_account["1300"] == (15.0, 0.0)
    assert by_account["2100"] == (0.0, 15.0)
    assert "1200" not in by_account
    assert "2000" not in by_account

    # Cancel reverses RC only
    cancelled = await ac.post(
        f"/api/v1/purchasing/invoices/{inv_id}/cancel", headers=headers
    )
    assert cancelled.status_code == 200, cancelled.text
    rev = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.source_type == "purchase_invoice_cancel",
                m.JournalEntry.source_id == inv_id,
            )
        )
    ).scalar_one()
    rev_lines = (
        await db_session.execute(
            select(m.JournalEntryLine).where(m.JournalEntryLine.journal_entry_id == rev.id)
        )
    ).scalars().all()
    rev_by = {}
    for ln in rev_lines:
        acct = (
            await db_session.execute(select(m.Account).where(m.Account.id == ln.account_id))
        ).scalar_one()
        rev_by[acct.code] = (float(ln.debit), float(ln.credit))
    assert set(rev_by) == {"1300", "2100"}
    assert rev_by["2100"] == (15.0, 0.0)
    assert rev_by["1300"] == (0.0, 15.0)

    # GRN AP balance still intact
    balance_after_cancel = float(
        (await ac.get(f"/api/v1/suppliers/{supplier_id}", headers=headers)).json()["data"][
            "balance"
        ]
    )
    assert balance_after_cancel == pytest.approx(100)
