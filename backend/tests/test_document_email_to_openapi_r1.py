"""Document email send Query `to` OpenAPI honesty (BR-7.4 / BR-7.2 / BR-6.3)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.emailer import clear_dev_outbox
from app.schemas import PurchaseOrderAmend
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_purchase_order_amend_to_emailstr():
    ok = PurchaseOrderAmend.model_validate(
        {"reason": "price change", "to": "  supplier@example.com  "}
    )
    assert str(ok.to) == "supplier@example.com"
    omit = PurchaseOrderAmend.model_validate({"reason": "notes only"})
    assert omit.to is None
    with pytest.raises(ValidationError):
        PurchaseOrderAmend.model_validate({"reason": "x", "to": ""})
    with pytest.raises(ValidationError):
        PurchaseOrderAmend.model_validate({"reason": "x", "to": "not-an-email"})


def test_document_email_to_ui_and_docs():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Document email override to"' in sales
    assert 'aria-label="Email quotation"' in sales
    assert 'aria-label="Email invoice"' in sales or 'aria-label={inv.emailed_at' in sales
    assert "docEmailTo" in sales
    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Purchase order email override to"' in purchasing
    assert 'aria-label="Email purchase order"' in purchasing
    assert 'aria-label="PO amend email override to"' in purchasing
    assert "poEmailTo" in purchasing
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Document email send Query `to` OpenAPI" in agents
    assert "EmailStr" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "sales/invoices/{invoice_id}/send" in docs
    assert "EmailStr" in docs
    assert "purchasing/orders/{po_id}/send" in docs


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_document_email_to_query_blank_invalid_422(client, seeded, monkeypatch):
    ac, seed = client
    admin = await _admin(ac, seed)
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")
    clear_dev_outbox()

    customer = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={
            "name": "Email To Honesty Buyer",
            "kind": "customer",
            "email": "buyer-to@example.com",
        },
    )
    assert customer.status_code == 200, customer.text
    customer_id = customer.json()["data"]["id"]

    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 10}],
        },
    )
    assert created.status_code == 200, created.text
    inv_id = created.json()["data"]["id"]
    posted = await ac.post(f"/api/v1/sales/invoices/{inv_id}/post", headers=admin)
    assert posted.status_code == 200, posted.text

    blank = await ac.post(
        f"/api/v1/sales/invoices/{inv_id}/send",
        headers=admin,
        params={"to": ""},
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.post(
        f"/api/v1/sales/invoices/{inv_id}/send",
        headers=admin,
        params={"to": "not-an-email"},
    )
    assert garbage.status_code == 422, garbage.text

    ok = await ac.post(
        f"/api/v1/sales/invoices/{inv_id}/send",
        headers=admin,
        params={"to": "override@example.com"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["emailed_to"] == "override@example.com"

    quote = await ac.post(
        "/api/v1/sales/quotations",
        headers=admin,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 8}],
        },
    )
    assert quote.status_code == 200, quote.text
    qid = quote.json()["data"]["id"]
    q_bad = await ac.post(
        f"/api/v1/sales/quotations/{qid}/send",
        headers=admin,
        params={"to": "bad"},
    )
    assert q_bad.status_code == 422, q_bad.text
    q_blank = await ac.post(
        f"/api/v1/sales/quotations/{qid}/send",
        headers=admin,
        params={"to": ""},
    )
    assert q_blank.status_code == 422, q_blank.text

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={
            "name": "Email To Honesty Vendor",
            "kind": "supplier",
            "email": "vendor-to@example.com",
        },
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]
    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=admin,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 4}],
        },
    )
    assert po.status_code == 200, po.text
    po_id = po.json()["data"]["id"]
    po_bad = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/send",
        headers=admin,
        params={"to": ""},
    )
    assert po_bad.status_code == 422, po_bad.text
    po_ok = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/send",
        headers=admin,
        params={"to": "po-override@example.com"},
    )
    assert po_ok.status_code == 200, po_ok.text
    assert po_ok.json()["data"]["emailed_to"] == "po-override@example.com"

    amend_bad = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/amend",
        headers=admin,
        json={"reason": "typo", "notify_supplier": True, "to": "not-an-email"},
    )
    assert amend_bad.status_code == 422, amend_bad.text
