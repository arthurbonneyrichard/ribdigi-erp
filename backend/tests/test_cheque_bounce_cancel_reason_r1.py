"""Cheque bounce/cancel reason honesty (BR-10.4) — JSON body `{ reason }` required."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app import accounting as accounting_svc
from app import models as m
from app import sales as sales_svc
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_cheque_bounce_cancel_reason_ui_wired():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "chequeActionReason" in page
    assert "Required before Bounce or Cancel" in page
    assert "JSON.stringify({ reason })" in page
    assert "?reason=" not in page
    assert "encodeURIComponent(reason)" not in page
    assert "Enter a reason before" in page
    assert "bouncing" in page
    assert "cancelling" in page
    assert 'aria-label="Cheque bounce cancel reason"' in page
    assert "aria-label={`Bounce cheque ${c.id}`}" in page
    assert "aria-label={`Cancel cheque ${c.id}`}" in page


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _pending_received_cheque(ac, db_session, seed, headers, *, number: str, amount: float = 50):
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    party = m.Party(
        tenant_id=tenant_id,
        name=f"Cheque Customer {number}",
        kind="customer",
        credit_limit=0,
        balance=amount,
    )
    db_session.add(party)
    await db_session.flush()

    inv = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number=f"INV-{number}",
        customer_id=party.id,
        status="posted",
        subtotal=amount,
        tax_amount=0,
        total_amount=amount,
        paid_amount=0,
        posted_at=__import__("datetime").datetime.utcnow(),
        created_by=seed["admin1"].id,
    )
    db_session.add(inv)
    await db_session.flush()

    await sales_svc.record_customer_payment(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["admin1"].id,
        customer_id=party.id,
        amount=amount,
        sales_invoice_id=inv.id,
        payment_method="cheque",
        reference=number,
        cheque_number=number,
        bank_name="First National",
    )
    await db_session.commit()

    listed = await ac.get("/api/v1/accounting/cheques", headers=headers)
    assert listed.status_code == 200, listed.text
    return next(c for c in listed.json()["data"] if c["cheque_number"] == number)


@pytest.mark.asyncio
async def test_bounce_cheque_requires_reason_and_persists(client, db_session, seeded):
    ac, seed = client
    headers = await _admin(ac, seed)
    chq = await _pending_received_cheque(
        ac, db_session, seed, headers, number="CHQ-REASON-1"
    )
    assert chq["status"] == "pending"

    missing = await ac.post(
        f"/api/v1/accounting/cheques/{chq['id']}/bounce",
        headers=headers,
        json={},
    )
    assert missing.status_code == 422

    empty = await ac.post(
        f"/api/v1/accounting/cheques/{chq['id']}/bounce",
        headers=headers,
        json={"reason": ""},
    )
    assert empty.status_code == 422

    blank = await ac.post(
        f"/api/v1/accounting/cheques/{chq['id']}/bounce",
        headers=headers,
        json={"reason": "   "},
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.post(
        f"/api/v1/accounting/cheques/{chq['id']}/bounce",
        headers=headers,
        json={"reason": "!!!!"},
    )
    assert garbage.status_code == 422, garbage.text

    # Query-string reason no longer accepted as the required body.
    query_only = await ac.post(
        f"/api/v1/accounting/cheques/{chq['id']}/bounce",
        headers=headers,
        params={"reason": "should not work as sole reason"},
    )
    assert query_only.status_code == 422

    bounced = await ac.post(
        f"/api/v1/accounting/cheques/{chq['id']}/bounce",
        headers=headers,
        json={"reason": "NSF — insufficient funds"},
    )
    assert bounced.status_code == 200, bounced.text
    body = bounced.json()["data"]
    assert body["status"] == "bounced"
    assert "NSF — insufficient funds" in (body.get("notes") or "")
    assert "Bounce:" in (body.get("notes") or "")


@pytest.mark.asyncio
async def test_cancel_issued_cheque_requires_reason(client, db_session, seeded):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    from app import cheques as cheques_svc

    supplier = m.Party(
        tenant_id=tenant_id,
        name="Cheque Cancel Supplier",
        kind="supplier",
        credit_limit=0,
        balance=200,
    )
    db_session.add(supplier)
    await db_session.flush()

    pay = m.SupplierPayment(
        tenant_id=tenant_id,
        payment_number="SPY-CHQ-CANCEL-1",
        supplier_id=supplier.id,
        amount=25,
        payment_method="cheque",
        reference="CHQ-CANCEL-1",
        created_by=seed["admin1"].id,
    )
    db_session.add(pay)
    await db_session.flush()
    await accounting_svc.post_supplier_payment_journal(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["admin1"].id,
        payment=pay,
    )
    chq = await cheques_svc.create_from_supplier_payment(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["admin1"].id,
        payment=pay,
        cheque_number="CHQ-CANCEL-1",
    )
    await db_session.commit()

    missing = await ac.post(
        f"/api/v1/accounting/cheques/{chq.id}/cancel",
        headers=headers,
        json={},
    )
    assert missing.status_code == 422

    ok = await ac.post(
        f"/api/v1/accounting/cheques/{chq.id}/cancel",
        headers=headers,
        json={"reason": "Stop payment — API hello-world"},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["status"] == "cancelled"
    assert "Stop payment — API hello-world" in (body.get("notes") or "")
    assert "Cancel:" in (body.get("notes") or "")
