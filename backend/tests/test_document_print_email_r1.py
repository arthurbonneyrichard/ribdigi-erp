"""Shared document print letterhead + branded email identity (quote/SO/returns/GRN/PI/PR)."""

from __future__ import annotations

import re
from pathlib import Path

import pyotp
import pytest

from app.emailer import clear_dev_outbox, get_dev_outbox
from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def _pdf_text(pdf: bytes) -> str:
    parts = []
    for raw in re.findall(rb"\((?:\\.|[^\\)])*\)", pdf):
        text = raw[1:-1].decode("latin-1")
        text = text.replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\")
        if text:
            parts.append(text)
    return "\n".join(parts)


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _brand_tenant(db_session, seed):
    tenant = await db_session.get(m.Tenant, seed["t1"].id)
    tenant.email = "accounts@alpha.example.com"
    tenant.phone = "+233201111111"
    tenant.address = "12 Market Street, Accra"
    tenant.legal_name = "Alpha Company Ltd"
    tenant.registration_number = "CS123456"
    tenant.tax_registration_number = "C0001234567"
    await db_session.commit()


def _assert_letterhead(html: str, heading: str):
    assert "doc-company" in html
    assert "doc-head letterhead" in html
    head = html.split("doc-head letterhead", 1)[1].split("doc-body", 1)[0]
    assert "Alpha Co" in head
    assert "Alpha Company Ltd" in head
    assert "12 Market Street, Accra" in head
    assert "Tel +233201111111" in head
    assert "accounts@alpha.example.com" in head
    assert "Reg CS123456" in head
    assert "TIN C0001234567" in head
    assert heading in html
    assert "invented@" not in html


def test_document_print_ui_and_docs():
    sales = (ROOT / "frontend" / "app" / "(dashboard)" / "sales" / "page.tsx").read_text(
        encoding="utf-8"
    )
    purchasing = (
        ROOT / "frontend" / "app" / "(dashboard)" / "purchasing" / "page.tsx"
    ).read_text(encoding="utf-8")
    credit = (ROOT / "frontend" / "app" / "(dashboard)" / "credit" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "ariaLabel: 'Print quotation'" in sales
    assert "ariaLabel: 'Email quotation'" in sales
    assert "/sales/quotations/${q.id}/print?format=pdf" in sales
    assert "ariaLabel: 'Print sales order'" in sales
    assert "ariaLabel: 'Print sales return'" in sales
    assert "ariaLabel: 'Email sales order'" in sales
    assert "ariaLabel: 'Email sales return'" in sales
    assert "'Email invoice'" in sales
    assert "ariaLabel: 'Print purchase request'" in purchasing
    assert "ariaLabel: 'Print goods received note'" in purchasing
    assert "ariaLabel: 'Print supplier bill'" in purchasing
    assert "ariaLabel: 'Email purchase request'" in purchasing
    assert "ariaLabel: 'Email goods received note'" in purchasing
    assert "ariaLabel: 'Email supplier bill'" in purchasing
    assert "/purchasing/returns/${r.id}/print?format=pdf" in purchasing
    assert "ariaLabel: 'Email purchase order'" in purchasing
    assert "ariaLabel: 'Print purchase order'" in purchasing
    assert "/sales/payments/" in credit and "/print?format=pdf" in credit
    assert "/purchasing/payments/" in credit
    assert "Email payment receipt" in credit
    expenses = (ROOT / "frontend" / "app" / "(dashboard)" / "expenses" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert 'aria-label="Print expense"' in expenses
    docs = (ROOT / "docs" / "API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "sales/quotations/{quotation_id}/print" in docs
    assert "purchasing/grn/{grn_id}/print" in docs
    assert "expenses/{expense_id}/print" in docs
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Document print letterhead" in agents
    assert "Branded document email identity" in agents
    assert "GET /expenses/{id}/print" in agents


@pytest.mark.asyncio
async def test_document_prints_share_company_letterhead(client, db_session, seeded):
    ac, seed = client
    admin = await _super(ac, seed)
    await _brand_tenant(db_session, seed)

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "Walk-in Letterhead Vendor"},
    )
    assert supplier.status_code == 200, supplier.text
    assert not (supplier.json()["data"].get("email") or "").strip()
    supplier_id = supplier.json()["data"]["id"]

    pr = await ac.post(
        "/api/v1/purchasing/requests",
        headers=admin,
        json={
            "items": [{"product_id": seed["p1"].id, "quantity": 2}],
            "notes": "Need stock for the shop",
        },
    )
    assert pr.status_code == 200, pr.text
    pr_id = pr.json()["data"]["id"]
    printed_pr = await ac.get(f"/api/v1/purchasing/requests/{pr_id}/print", headers=admin)
    assert printed_pr.status_code == 200, printed_pr.text
    assert "text/html" in printed_pr.headers.get("content-type", "")
    _assert_letterhead(printed_pr.text, "Purchase request")
    assert seed["p1"].name in printed_pr.text or seed["p1"].sku in printed_pr.text
    bad_pr = await ac.get(
        f"/api/v1/purchasing/requests/{pr_id}/print?format=docx", headers=admin
    )
    assert bad_pr.status_code == 422

    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=admin,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 5}],
        },
    )
    assert po.status_code == 200, po.text
    po_id = po.json()["data"]["id"]
    issued = await ac.post(f"/api/v1/purchasing/orders/{po_id}/issue", headers=admin)
    assert issued.status_code == 200, issued.text

    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=admin,
        json={
            "purchase_order_id": po_id,
            "items": [
                {
                    "po_item_id": issued.json()["data"]["items"][0]["id"],
                    "received_qty": 2,
                    "accepted_qty": 2,
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    grn_id = grn.json()["data"]["id"]
    printed_grn = await ac.get(f"/api/v1/purchasing/grn/{grn_id}/print", headers=admin)
    assert printed_grn.status_code == 200, printed_grn.text
    _assert_letterhead(printed_grn.text, "Goods received")
    assert "Supplier email" not in printed_grn.text

    bill = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=admin,
        json={"goods_receipt_id": grn_id},
    )
    assert bill.status_code == 200, bill.text
    bill_id = bill.json()["data"]["id"]
    printed_bill = await ac.get(
        f"/api/v1/purchasing/invoices/{bill_id}/print?format=pdf", headers=admin
    )
    assert printed_bill.status_code == 200, printed_bill.text
    assert printed_bill.headers.get("content-type", "").startswith("application/pdf")
    pdf_text = _pdf_text(printed_bill.content)
    assert pdf_text.index("Alpha Co") < pdf_text.index("SUPPLIER BILL")
    assert pdf_text.index("accounts@alpha.example.com") < pdf_text.index("SUPPLIER BILL")

    ret = await ac.post(
        "/api/v1/purchasing/returns",
        headers=admin,
        json={
            "goods_receipt_id": grn_id,
            "reason": "damaged",
            "items": [
                {
                    "goods_receipt_item_id": grn.json()["data"]["items"][0]["id"],
                    "quantity": 1,
                }
            ],
        },
    )
    assert ret.status_code == 200, ret.text
    printed_ret = await ac.get(
        f"/api/v1/purchasing/returns/{ret.json()['data']['id']}/print", headers=admin
    )
    assert printed_ret.status_code == 200, printed_ret.text
    _assert_letterhead(printed_ret.text, "Purchase return")

    approved = await ac.post(
        f"/api/v1/purchasing/invoices/{bill_id}/approve", headers=admin, json={}
    )
    assert approved.status_code == 200, approved.text
    pay = await ac.post(
        f"/api/v1/suppliers/{supplier_id}/payments",
        headers=admin,
        json={
            "supplier_id": supplier_id,
            "purchase_invoice_id": bill_id,
            "amount": 2,
            "payment_method": "cash",
        },
    )
    assert pay.status_code == 200, pay.text
    printed_pay = await ac.get(
        f"/api/v1/purchasing/payments/{pay.json()['data']['id']}/print", headers=admin
    )
    assert printed_pay.status_code == 200, printed_pay.text
    _assert_letterhead(printed_pay.text, "Supplier payment")

    quote = await ac.post(
        "/api/v1/sales/quotations",
        headers=admin,
        json={
            "customer_id": seed["party1"].id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 8}],
        },
    )
    assert quote.status_code == 200, quote.text
    qid = quote.json()["data"]["id"]
    printed_q = await ac.get(f"/api/v1/sales/quotations/{qid}/print", headers=admin)
    assert printed_q.status_code == 200, printed_q.text
    _assert_letterhead(printed_q.text, "Quotation")
    assert "Customer email" not in printed_q.text
    missing_q = await ac.post(f"/api/v1/sales/quotations/{qid}/send", headers=admin)
    assert missing_q.status_code == 400
    assert "email" in missing_q.json()["detail"].lower()

    order = await ac.post(
        "/api/v1/sales/orders",
        headers=admin,
        json={
            "customer_id": seed["party1"].id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 8}],
        },
    )
    assert order.status_code == 200, order.text
    printed_so = await ac.get(
        f"/api/v1/sales/orders/{order.json()['data']['id']}/print?format=pdf",
        headers=admin,
    )
    assert printed_so.status_code == 200, printed_so.text
    so_text = _pdf_text(printed_so.content)
    assert so_text.index("Alpha Co") < so_text.index("SALES ORDER")
    assert so_text.index("accounts@alpha.example.com") < so_text.index("SALES ORDER")

    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={
            "customer_id": seed["party1"].id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 20}],
        },
    )
    assert inv.status_code == 200, inv.text
    iid = inv.json()["data"]["id"]
    posted = await ac.post(f"/api/v1/sales/invoices/{iid}/post", headers=admin)
    assert posted.status_code == 200, posted.text

    sret = await ac.post(
        "/api/v1/sales/returns",
        headers=admin,
        json={
            "sales_invoice_id": iid,
            "reason": "damaged",
            "items": [
                {"product_id": seed["p1"].id, "quantity": 1, "condition": "discard"}
            ],
        },
    )
    assert sret.status_code == 200, sret.text
    printed_sr = await ac.get(
        f"/api/v1/sales/returns/{sret.json()['data']['id']}/print", headers=admin
    )
    assert printed_sr.status_code == 200, printed_sr.text
    _assert_letterhead(printed_sr.text, "Sales return")

    cpay = await ac.post(
        "/api/v1/sales/payments",
        headers=admin,
        json={
            "customer_id": seed["party1"].id,
            "sales_invoice_id": iid,
            "amount": 5,
            "payment_method": "cash",
        },
    )
    assert cpay.status_code == 200, cpay.text
    printed_cpay = await ac.get(
        f"/api/v1/sales/payments/{cpay.json()['data']['id']}/print", headers=admin
    )
    assert printed_cpay.status_code == 200, printed_cpay.text
    _assert_letterhead(printed_cpay.text, "Payment receipt")

    still_no_email = await ac.get(f"/api/v1/customers/{seed['party1'].id}", headers=admin)
    assert still_no_email.status_code == 200
    assert not (still_no_email.json()["data"].get("email") or "").strip()


@pytest.mark.asyncio
async def test_quotation_email_header_includes_company_identity(
    client, db_session, monkeypatch
):
    ac, seed = client
    admin = await _super(ac, seed)
    await _brand_tenant(db_session, seed)
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")
    clear_dev_outbox()

    customer = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": "Quote Letterhead Buyer", "email": "buyer@example.com"},
    )
    assert customer.status_code == 200, customer.text
    quote = await ac.post(
        "/api/v1/sales/quotations",
        headers=admin,
        json={
            "customer_id": customer.json()["data"]["id"],
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 8}],
        },
    )
    assert quote.status_code == 200, quote.text
    sent = await ac.post(
        f"/api/v1/sales/quotations/{quote.json()['data']['id']}/send", headers=admin
    )
    assert sent.status_code == 200, sent.text
    out = get_dev_outbox()
    assert out
    html_body = out[0]["html_body"]
    brand = html_body.split("ribdigi-email-brand", 1)[1].split("padding:24px;", 1)[0]
    assert "Alpha Co" in brand
    assert "accounts@alpha.example.com" in brand
    assert "ribdigi-email-identity" in brand
    assert "Alpha Widget" in html_body or seed["p1"].name in html_body
    assert "Valid until" in html_body or "Quote date" in html_body
    assert out[0]["to"] == ["buyer@example.com"]
