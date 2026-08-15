"""Cheque bounce/cancel reason honesty (BR-10.4) — FE sends ?reason=."""

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
    assert "encodeURIComponent(reason)" in page
    assert "?reason=" in page
    assert "Enter a reason before" in page
    assert "bouncing" in page
    assert "cancelling" in page


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_bounce_cheque_reason_query_persists_notes(client, db_session, seeded):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    party = m.Party(
        tenant_id=tenant_id,
        name="Cheque Reason Customer",
        kind="customer",
        credit_limit=0,
        balance=50,
    )
    db_session.add(party)
    await db_session.flush()

    inv = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number="INV-CHQ-REASON-1",
        customer_id=party.id,
        status="posted",
        subtotal=50,
        tax_amount=0,
        total_amount=50,
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
        amount=50,
        sales_invoice_id=inv.id,
        payment_method="cheque",
        reference="CHQ-REASON-1",
        cheque_number="CHQ-REASON-1",
        bank_name="First National",
    )
    await db_session.commit()

    listed = await ac.get("/api/v1/accounting/cheques", headers=headers)
    assert listed.status_code == 200, listed.text
    chq = next(c for c in listed.json()["data"] if c["cheque_number"] == "CHQ-REASON-1")
    assert chq["status"] == "pending"

    bounced = await ac.post(
        f"/api/v1/accounting/cheques/{chq['id']}/bounce",
        headers=headers,
        params={"reason": "NSF — insufficient funds"},
    )
    assert bounced.status_code == 200, bounced.text
    body = bounced.json()["data"]
    assert body["status"] == "bounced"
    assert "NSF — insufficient funds" in (body.get("notes") or "")
