"""Stage 11 A1: purchasing chain domain audit (GRN, payment, PI cancel)."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import audit as audit_svc
from app import models as m
from app import purchasing as purchasing_svc
from tests.conftest import auth_headers


async def _super_headers(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_grn_payment_cancel_audited_with_hash(client, db_session):
    ac, seed = client
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    supplier = m.Party(
        tenant_id=tenant_id,
        name="Audit Chain Sup",
        kind="supplier",
        credit_limit=0,
        balance=0,
    )
    db_session.add(supplier)
    await db_session.flush()

    po = await purchasing_svc.create_purchase_order(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["admin1"].id,
        supplier_id=supplier.id,
        items=[
            {
                "product_id": seed["p1"].id,
                "quantity": 4,
                "unit_price": 25,
                "tax_rate": 0,
            }
        ],
    )
    po, _email = await purchasing_svc.send_purchase_order(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["admin1"].id,
        po_id=po.id,
        email=False,
    )
    items = await purchasing_svc.list_po_items(db_session, tenant_id, po.id)
    grn = await purchasing_svc.create_grn(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["admin1"].id,
        purchase_order_id=po.id,
        items=[
            {
                "po_item_id": items[0].id,
                "received_qty": 4,
                "accepted_qty": 4,
            }
        ],
    )
    await db_session.flush()

    headers = await _super_headers(ac, seed)
    grn_logs = await ac.get(
        "/api/v1/audit-logs",
        headers=headers,
        params={"action": "grn_posted"},
    )
    assert grn_logs.status_code == 200, grn_logs.text
    grow = next(r for r in grn_logs.json()["data"] if r["entity_id"] == grn.id)
    assert grow["integrity_hash"]
    assert grow["module"] == "purchasing"
    assert grow["details"]["accepted_value"] == 100
    assert grow["details"]["supplier_balance_after"] == 100

    journals = await ac.get(
        "/api/v1/audit-logs",
        headers=headers,
        params={"action": "journal_posted"},
    )
    assert journals.status_code == 200
    assert any(
        (r.get("details") or {}).get("source_type") == "grn"
        and (r.get("details") or {}).get("source_id") == grn.id
        for r in journals.json()["data"]
    )

    inv = await purchasing_svc.create_purchase_invoice(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["admin1"].id,
        goods_receipt_id=grn.id,
    )
    inv = await purchasing_svc.approve_purchase_invoice(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["admin1"].id,
        invoice_id=inv.id,
    )
    payment = await purchasing_svc.record_supplier_payment(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["admin1"].id,
        supplier_id=supplier.id,
        amount=100,
        purchase_invoice_id=inv.id,
        payment_method="bank_transfer",
    )
    await db_session.commit()

    pay_logs = await ac.get(
        "/api/v1/audit-logs",
        headers=headers,
        params={"action": "supplier_payment_recorded"},
    )
    assert pay_logs.status_code == 200, pay_logs.text
    prow = next(r for r in pay_logs.json()["data"] if r["entity_id"] == payment.id)
    assert prow["integrity_hash"]
    assert prow["module"] == "purchasing"
    assert float(prow["details"]["amount"]) == 100

    # Separate cancel path on a manual unpaid PI
    inv2 = await purchasing_svc.create_purchase_invoice(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["admin1"].id,
        supplier_id=supplier.id,
        items=[{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 10, "tax_rate": 0}],
    )
    inv2 = await purchasing_svc.approve_purchase_invoice(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["admin1"].id,
        invoice_id=inv2.id,
    )
    await purchasing_svc.cancel_purchase_invoice(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["admin1"].id,
        invoice_id=inv2.id,
    )
    await db_session.commit()

    cancel_logs = await ac.get(
        "/api/v1/audit-logs",
        headers=headers,
        params={"action": "purchase_invoice_cancelled"},
    )
    assert cancel_logs.status_code == 200, cancel_logs.text
    crow = next(r for r in cancel_logs.json()["data"] if r["entity_id"] == inv2.id)
    assert crow["integrity_hash"]
    assert crow["details"]["prior_status"] in {"unpaid", "overdue"}

    chain = await audit_svc.verify_chain(db_session, tenant_id)
    assert chain["valid"] is True
