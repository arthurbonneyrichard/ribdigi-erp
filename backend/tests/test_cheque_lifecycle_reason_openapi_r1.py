"""ChequeLifecycleReason.reason OpenAPI honesty (BR-10.4)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app import accounting as accounting_svc
from app import models as m
from app import sales as sales_svc
from app.schemas import ChequeLifecycleReason
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_cheque_lifecycle_reason_schema():
    ok = ChequeLifecycleReason.model_validate({"reason": "  NSF insufficient funds  "})
    assert ok.reason == "NSF insufficient funds"
    for bad in ("", " ", "!!!", "!!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            ChequeLifecycleReason.model_validate({"reason": bad})
    with pytest.raises(ValidationError):
        ChequeLifecycleReason.model_validate({})


def test_cheque_lifecycle_reason_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Cheque bounce cancel reason"' in page
    assert "chequeActionReason" in page
    assert "aria-label={`Bounce cheque ${c.id}`}" in page
    assert "aria-label={`Cancel cheque ${c.id}`}" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "ChequeLifecycleReasonValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "ChequeLifecycleReasonValue" in docs


@pytest.mark.asyncio
async def test_cheque_lifecycle_reason_api_blank_invalid_422(client, db_session, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]
    tag = f"TIP203 bounce {suffix}"
    number = f"CHQ-TIP203-{suffix[:6]}"

    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    party = m.Party(
        tenant_id=tenant_id,
        name=f"Tip203 Customer {suffix}",
        kind="customer",
        credit_limit=0,
        balance=40,
    )
    db_session.add(party)
    await db_session.flush()
    inv = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number=f"INV-TIP203-{suffix[:6]}",
        customer_id=party.id,
        status="posted",
        subtotal=40,
        tax_amount=0,
        total_amount=40,
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
        amount=40,
        sales_invoice_id=inv.id,
        payment_method="cheque",
        reference=number,
        cheque_number=number,
        bank_name="First National",
    )
    await db_session.commit()

    listed = await ac.get("/api/v1/accounting/cheques", headers=headers)
    assert listed.status_code == 200, listed.text
    chq = next(c for c in listed.json()["data"] if c["cheque_number"] == number)

    for bad in ("", "!!!", "http://evil", "   "):
        resp = await ac.post(
            f"/api/v1/accounting/cheques/{chq['id']}/bounce",
            headers=headers,
            json={"reason": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        f"/api/v1/accounting/cheques/{chq['id']}/bounce",
        headers=headers,
        json={"reason": tag},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["status"] == "bounced"
    assert tag in (body.get("notes") or "")
    assert "Bounce:" in (body.get("notes") or "")
