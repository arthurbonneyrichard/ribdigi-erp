"""Purchase order print and paper issue (no supplier email)."""

from __future__ import annotations

import re
from pathlib import Path

import pyotp
import pytest

from app.emailer import clear_dev_outbox
from app.invoice_print import to_invoice_a4_pdf, to_purchase_order_a4_pdf
from app.rbac import permissions_for_role
from app.security import hash_password
from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def _pdf_text_in_order(pdf: bytes) -> str:
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


async def _seed_io(db_session, seed):
    user = m.User(
        tenant_id=seed["t1"].id,
        email="io-po-print@alpha.example.com",
        full_name="IO PO Print",
        password_hash=hash_password("SecurePass123!"),
        role="inventory_officer",
        email_verified=True,
        permissions=permissions_for_role("inventory_officer"),
        totp_enabled=False,
    )
    db_session.add(user)
    await db_session.commit()
    return user


def test_po_print_ui_and_docs():
    purchasing = (
        ROOT / "frontend" / "app" / "(dashboard)" / "purchasing" / "page.tsx"
    ).read_text(encoding="utf-8")
    assert "ariaLabel: 'Print purchase order'" in purchasing
    assert "aria-label={`Print purchase order ${selected.id}`}" in purchasing
    assert "/purchasing/orders/${current.id}/print?format=pdf" in purchasing
    assert "openDocumentPrint" in purchasing
    printer = (ROOT / "frontend" / "lib" / "documentPrint.ts").read_text(encoding="utf-8")
    assert "apiFetch" in printer
    assert "content-type" in printer and "pdf" in printer
    assert "/purchasing/orders/${po.id}/issue" in purchasing
    assert "Email or print a purchase order" in purchasing
    assert "Hand the paper to the supplier" in purchasing
    assert "ariaLabel: 'Email purchase order'" in purchasing
    assert "aria-label={`Email purchase order ${selected.id}`}" in purchasing
    docs = (ROOT / "docs" / "API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "purchasing/orders/{po_id}/print" in docs
    assert "purchasing/orders/{po_id}/issue" in docs
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Purchase order print / paper issue" in agents


@pytest.mark.asyncio
async def test_print_and_issue_without_supplier_email_then_grn(client, db_session, monkeypatch):
    ac, seed = client
    await _seed_io(db_session, seed)
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-po-print@alpha.example.com", tenant_slug="alpha")
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    clear_dev_outbox()

    tenant = await db_session.get(m.Tenant, seed["t1"].id)
    tenant.email = "accounts@alpha.example.com"
    tenant.phone = "+233201111111"
    tenant.address = "12 Market Street, Accra"
    tenant.legal_name = "Alpha Company Ltd"
    tenant.registration_number = "CS123456"
    tenant.tax_registration_number = "C0001234567"
    await db_session.commit()

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "Walk-in Paper Vendor"},
    )
    assert supplier.status_code == 200, supplier.text
    assert not (supplier.json()["data"].get("email") or "").strip()

    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=io,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "items": [{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 5}],
            "notes": "Hand this paper to the driver",
        },
    )
    assert created.status_code == 200, created.text
    po = created.json()["data"]
    po_id = po["id"]
    assert po["status"] == "draft"

    missing = await ac.post(f"/api/v1/purchasing/orders/{po_id}/send", headers=io)
    assert missing.status_code == 400
    assert "email" in missing.json()["detail"].lower()

    printed = await ac.get(f"/api/v1/purchasing/orders/{po_id}/print", headers=io)
    assert printed.status_code == 200, printed.text
    assert "text/html" in printed.headers.get("content-type", "")
    html = printed.text
    assert po["po_number"] in html
    assert "Walk-in Paper Vendor" in html
    assert "Hand this paper to the driver" in html
    assert seed["p1"].name in html or seed["p1"].sku in html
    assert "Order date" in html
    assert "Needed by" in html or "Order date" in html
    assert "Due " not in html
    assert "doc-company" in html
    assert "doc-head letterhead" in html
    assert ".doc-head, .doc-head .doc-company, .doc-company" in html
    assert "visibility: visible !important" in html
    assert ".toolbar { display: none; }" in html
    head = html.split("doc-head letterhead", 1)[1].split("doc-body", 1)[0]
    assert "Alpha Co" in head
    assert "Alpha Company Ltd" in head
    assert "12 Market Street, Accra" in head
    assert "Tel +233201111111" in head
    assert "accounts@alpha.example.com" in head
    assert "Reg CS123456" in head
    assert "TIN C0001234567" in head
    assert "Alpha Co" in html
    assert "Alpha Company Ltd" in html
    assert "12 Market Street, Accra" in html
    assert "Tel +233201111111" in html
    assert "accounts@alpha.example.com" in html
    assert "Reg CS123456" in html
    assert "TIN C0001234567" in html
    assert "Supplier email" not in html

    denied_fmt = await ac.get(
        f"/api/v1/purchasing/orders/{po_id}/print?format=docx", headers=io
    )
    assert denied_fmt.status_code == 422
    blank_fmt = await ac.get(f"/api/v1/purchasing/orders/{po_id}/print?format=", headers=io)
    assert blank_fmt.status_code == 422

    pdf_res = await ac.get(
        f"/api/v1/purchasing/orders/{po_id}/print?format=pdf", headers=io
    )
    assert pdf_res.status_code == 200, pdf_res.text
    assert pdf_res.headers.get("content-type", "").startswith("application/pdf")
    assert pdf_res.content.startswith(b"%PDF")
    pdf_text = _pdf_text_in_order(pdf_res.content)
    assert pdf_text.index("Alpha Co") < pdf_text.index("PURCHASE ORDER")
    assert pdf_text.index("accounts@alpha.example.com") < pdf_text.index("PURCHASE ORDER")
    assert "12 Market Street, Accra" in pdf_text
    assert "Tel +233201111111" in pdf_text
    assert po["po_number"] in pdf_text
    assert "Walk-in Paper Vendor" in pdf_text
    still_draft = await ac.get(f"/api/v1/purchasing/orders/{po_id}", headers=io)
    assert still_draft.json()["data"]["status"] == "draft"
    assert not still_draft.json()["data"].get("emailed_to")

    issued = await ac.post(f"/api/v1/purchasing/orders/{po_id}/issue", headers=io)
    assert issued.status_code == 200, issued.text
    body = issued.json()["data"]
    assert body["status"] == "sent"
    assert not body.get("emailed_to")
    assert not body.get("emailed_at")

    again = await ac.post(f"/api/v1/purchasing/orders/{po_id}/issue", headers=io)
    assert again.status_code == 200, again.text
    assert again.json()["data"]["status"] == "sent"

    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=io,
        json={
            "purchase_order_id": po_id,
            "items": [
                {
                    "po_item_id": body["items"][0]["id"],
                    "received_qty": 2,
                    "accepted_qty": 2,
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    assert grn.json()["data"]["status"] == "posted"


@pytest.mark.asyncio
async def test_issue_rejected_after_cancel_and_print_stays_readable(client, db_session):
    ac, seed = client
    await _seed_io(db_session, seed)
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-po-print@alpha.example.com", tenant_slug="alpha")

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "Cancelled Paper Vendor"},
    )
    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=io,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 3}],
        },
    )
    po_id = created.json()["data"]["id"]
    cancelled = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/cancel",
        headers=io,
        json={"reason": "Supplier walked away"},
    )
    assert cancelled.status_code == 200, cancelled.text
    blocked = await ac.post(f"/api/v1/purchasing/orders/{po_id}/issue", headers=io)
    assert blocked.status_code == 409
    printed = await ac.get(f"/api/v1/purchasing/orders/{po_id}/print", headers=io)
    assert printed.status_code == 200, printed.text
    assert created.json()["data"]["po_number"] in printed.text


@pytest.mark.asyncio
async def test_print_includes_supplier_email_when_present(client, db_session):
    ac, seed = client
    await _seed_io(db_session, seed)
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-po-print@alpha.example.com", tenant_slug="alpha")

    tenant = await db_session.get(m.Tenant, seed["t1"].id)
    tenant.email = "buyers@alpha.example.com"
    await db_session.commit()

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "Emailed Paper Vendor", "email": "vendor@paper.example.com"},
    )
    assert supplier.status_code == 200, supplier.text
    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=io,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 4}],
        },
    )
    assert created.status_code == 200, created.text
    printed = await ac.get(
        f"/api/v1/purchasing/orders/{created.json()['data']['id']}/print",
        headers=io,
    )
    assert printed.status_code == 200, printed.text
    html = printed.text
    assert "Alpha Co" in html
    assert "buyers@alpha.example.com" in html
    assert "Emailed Paper Vendor" in html
    assert "Supplier email vendor@paper.example.com" in html
    head = html.split("doc-head letterhead", 1)[1].split("doc-body", 1)[0]
    assert "Alpha Co" in head
    assert "buyers@alpha.example.com" in head


def test_po_and_invoice_pdf_header_share_company_block():
    invoice = to_invoice_a4_pdf(
        {
            "company_name": "Sunrise Mart",
            "company_email": "hello@sunrise.example.com",
            "company_address": "9 Harbor Ave",
            "company_phone": "+233201111000",
            "invoice_number": "I260812-001",
            "status": "posted",
            "customer_name": "Walk-in",
            "currency": "GHS",
            "subtotal": 10,
            "tax": 1.5,
            "total": 11.5,
            "items": [
                {
                    "name": "Water 500ml",
                    "quantity": 2,
                    "unit_price": 5,
                    "tax_rate": 15,
                    "line_total": 11.5,
                }
            ],
        }
    )
    po = to_purchase_order_a4_pdf(
        {
            "company_name": "Sunrise Mart",
            "company_email": "hello@sunrise.example.com",
            "company_address": "9 Harbor Ave",
            "company_phone": "+233201111000",
            "store_name": "Accra Shop",
            "po_number": "PO-1",
            "status": "sent",
            "supplier_name": "Rice Mill",
            "currency": "GHS",
            "subtotal": 10,
            "tax": 0,
            "total": 10,
            "items": [
                {
                    "name": "Rice 5kg",
                    "quantity": 2,
                    "unit_price": 5,
                    "tax_rate": 0,
                    "line_total": 10,
                }
            ],
        }
    )
    inv_text = _pdf_text_in_order(invoice)
    po_text = _pdf_text_in_order(po)
    assert inv_text.index("Sunrise Mart") < inv_text.index("SALES INVOICE")
    assert "hello@sunrise.example.com" in inv_text
    assert po_text.index("Sunrise Mart") < po_text.index("PURCHASE ORDER")
    assert po_text.index("hello@sunrise.example.com") < po_text.index("PURCHASE ORDER")
    assert po_text.index("9 Harbor Ave") < po_text.index("PURCHASE ORDER")
    assert po_text.index("Tel +233201111000") < po_text.index("PURCHASE ORDER")
    assert po_text.index("Accra Shop") < po_text.index("PURCHASE ORDER")
    assert "Rice Mill" in po_text
    assert invoice.startswith(b"%PDF")
    assert po.startswith(b"%PDF")
