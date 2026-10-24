"""New document Email Send paths + expense print (letterhead / OpenAPI honesty)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app import models as m
from app.emailer import clear_dev_outbox, get_dev_outbox
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def _pdf_text(pdf: bytes) -> str:
    import re

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


def _enable_console_email(monkeypatch):
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")
    clear_dev_outbox()


def _assert_branded(html: str, *needles: str):
    assert "ribdigi-email-identity" in html
    brand = html.split("ribdigi-email-brand", 1)[1].split("padding:24px;", 1)[0]
    assert "Alpha Co" in brand
    assert "accounts@alpha.example.com" in brand
    for needle in needles:
        assert needle in html


def test_document_send_ui_and_docs():
    sales = (ROOT / "frontend/app/(dashboard)/sales/page.tsx").read_text(encoding="utf-8")
    purchasing = (ROOT / "frontend/app/(dashboard)/purchasing/page.tsx").read_text(
        encoding="utf-8"
    )
    credit = (ROOT / "frontend/app/(dashboard)/credit/page.tsx").read_text(encoding="utf-8")
    expenses = (ROOT / "frontend/app/(dashboard)/expenses/page.tsx").read_text(
        encoding="utf-8"
    )
    assert "ariaLabel: 'Email sales order'" in sales
    assert "ariaLabel: 'Email sales return'" in sales
    assert 'aria-label="Document email override to"' in sales
    assert "ariaLabel: 'Email purchase request'" in purchasing
    assert "ariaLabel: 'Email goods received note'" in purchasing
    assert "ariaLabel: 'Email supplier bill'" in purchasing
    assert "ariaLabel: 'Email purchase return'" in purchasing
    assert "sendPurchasingDoc" in purchasing
    assert "Email payment receipt" in credit
    assert "Email supplier payment receipt" in credit
    assert 'aria-label="Document email override to"' in credit
    assert 'aria-label="Print expense"' in expenses
    assert "/expenses/${r.id}/print?format=pdf" in expenses
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Document email send Query `to` OpenAPI" in agents
    assert "sales/orders/{id}/send" in agents
    assert "GET /expenses/{id}/print" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "sales/orders/{order_id}/send" in docs
    assert "purchasing/grn/{grn_id}/send" in docs
    assert "expenses/{expense_id}/print" in docs
    assert "sales/payments/{payment_id}/send" in docs


@pytest.mark.asyncio
async def test_document_send_happy_422_400_isolation(client, db_session, seeded, monkeypatch):
    ac, seed = client
    admin = await _super(ac, seed)
    await _brand_tenant(db_session, seed)
    _enable_console_email(monkeypatch)

    beta_admin = m.User(
        tenant_id=seed["t2"].id,
        email="docsend-admin@beta.example.com",
        full_name="Beta Docsend Admin",
        password_hash=hash_password("SecurePass123!"),
        role="company_admin",
        email_verified=True,
        permissions=permissions_for_role("company_admin"),
        totp_enabled=False,
    )
    db_session.add(beta_admin)
    await db_session.commit()
    beta = await auth_headers(ac, email="docsend-admin@beta.example.com", tenant_slug="beta")

    customer = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": "Docsend Buyer", "email": "docsend-buyer@example.com"},
    )
    assert customer.status_code == 200, customer.text
    customer_id = customer.json()["data"]["id"]

    silent_customer = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": "Docsend Silent Buyer"},
    )
    assert silent_customer.status_code == 200, silent_customer.text
    silent_id = silent_customer.json()["data"]["id"]

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "Docsend Vendor", "email": "docsend-vendor@example.com"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    silent_supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "Docsend Silent Vendor"},
    )
    assert silent_supplier.status_code == 200, silent_supplier.text
    silent_supplier_id = silent_supplier.json()["data"]["id"]

    async def send_ok(path: str, *, expect: str, product: bool = True):
        clear_dev_outbox()
        resp = await ac.post(path, headers=admin)
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["delivery"]["to"] == expect
        assert data["delivery"]["mode"] == "console"
        out = get_dev_outbox()
        assert out and out[0]["to"] == [expect]
        _assert_branded(out[0]["html_body"], "Alpha Co")
        if product:
            assert "Alpha Widget" in out[0]["html_body"] or "Alpha Widget" in out[0]["text_body"]
            assert seed["p1"].id not in out[0]["text_body"]
        return data

    order = await ac.post(
        "/api/v1/sales/orders",
        headers=admin,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 8}],
        },
    )
    assert order.status_code == 200, order.text
    oid = order.json()["data"]["id"]
    await send_ok(f"/api/v1/sales/orders/{oid}/send", expect="docsend-buyer@example.com")
    garbage = await ac.post(
        f"/api/v1/sales/orders/{oid}/send", headers=admin, params={"to": "not-an-email"}
    )
    assert garbage.status_code == 422, garbage.text
    blank = await ac.post(f"/api/v1/sales/orders/{oid}/send", headers=admin, params={"to": ""})
    assert blank.status_code == 422, blank.text
    isolated = await ac.post(f"/api/v1/sales/orders/{oid}/send", headers=beta)
    assert isolated.status_code == 404, isolated.text

    silent_order = await ac.post(
        "/api/v1/sales/orders",
        headers=admin,
        json={
            "customer_id": silent_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 8}],
        },
    )
    assert silent_order.status_code == 200, silent_order.text
    missing = await ac.post(
        f"/api/v1/sales/orders/{silent_order.json()['data']['id']}/send", headers=admin
    )
    assert missing.status_code == 400, missing.text
    assert "email" in missing.json()["detail"].lower()

    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={
            "customer_id": customer_id,
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
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "condition": "discard"}],
        },
    )
    assert sret.status_code == 200, sret.text
    srid = sret.json()["data"]["id"]
    await send_ok(f"/api/v1/sales/returns/{srid}/send", expect="docsend-buyer@example.com")
    sr_bad = await ac.post(
        f"/api/v1/sales/returns/{srid}/send", headers=admin, params={"to": "!!!"}
    )
    assert sr_bad.status_code == 422, sr_bad.text

    cpay = await ac.post(
        "/api/v1/sales/payments",
        headers=admin,
        json={
            "customer_id": customer_id,
            "sales_invoice_id": iid,
            "amount": 5,
            "payment_method": "cash",
        },
    )
    assert cpay.status_code == 200, cpay.text
    cpay_id = cpay.json()["data"]["id"]
    await send_ok(
        f"/api/v1/sales/payments/{cpay_id}/send",
        expect="docsend-buyer@example.com",
        product=False,
    )
    cpay_iso = await ac.post(f"/api/v1/sales/payments/{cpay_id}/send", headers=beta)
    assert cpay_iso.status_code == 404, cpay_iso.text

    silent_inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={
            "customer_id": silent_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 6}],
        },
    )
    assert silent_inv.status_code == 200, silent_inv.text
    silent_posted = await ac.post(
        f"/api/v1/sales/invoices/{silent_inv.json()['data']['id']}/post", headers=admin
    )
    assert silent_posted.status_code == 200, silent_posted.text
    silent_pay = await ac.post(
        "/api/v1/sales/payments",
        headers=admin,
        json={
            "customer_id": silent_id,
            "sales_invoice_id": silent_inv.json()["data"]["id"],
            "amount": 1,
            "payment_method": "cash",
        },
    )
    assert silent_pay.status_code == 200, silent_pay.text
    silent_pay_miss = await ac.post(
        f"/api/v1/sales/payments/{silent_pay.json()['data']['id']}/send", headers=admin
    )
    assert silent_pay_miss.status_code == 400, silent_pay_miss.text

    pr = await ac.post(
        "/api/v1/purchasing/requests",
        headers=admin,
        json={
            "preferred_supplier_id": supplier_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 2}],
            "notes": "Need stock for the shop",
        },
    )
    assert pr.status_code == 200, pr.text
    prid = pr.json()["data"]["id"]
    await send_ok(f"/api/v1/purchasing/requests/{prid}/send", expect="docsend-vendor@example.com")

    requester = await db_session.get(m.User, seed["super"].id)
    previous_email = requester.email
    requester.email = ""
    await db_session.commit()
    pr_silent = await ac.post(
        "/api/v1/purchasing/requests",
        headers=admin,
        json={"items": [{"product_id": seed["p1"].id, "quantity": 1}]},
    )
    assert pr_silent.status_code == 200, pr_silent.text
    pr_miss = await ac.post(
        f"/api/v1/purchasing/requests/{pr_silent.json()['data']['id']}/send", headers=admin
    )
    assert pr_miss.status_code == 400, pr_miss.text
    requester = await db_session.get(m.User, seed["super"].id)
    requester.email = previous_email
    await db_session.commit()

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
    await send_ok(f"/api/v1/purchasing/grn/{grn_id}/send", expect="docsend-vendor@example.com")
    grn_bad = await ac.post(
        f"/api/v1/purchasing/grn/{grn_id}/send", headers=admin, params={"to": "bad"}
    )
    assert grn_bad.status_code == 422, grn_bad.text

    bill = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=admin,
        json={"goods_receipt_id": grn_id},
    )
    assert bill.status_code == 200, bill.text
    bill_id = bill.json()["data"]["id"]
    await send_ok(
        f"/api/v1/purchasing/invoices/{bill_id}/send", expect="docsend-vendor@example.com"
    )

    pret = await ac.post(
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
    assert pret.status_code == 200, pret.text
    pret_id = pret.json()["data"]["id"]
    await send_ok(
        f"/api/v1/purchasing/returns/{pret_id}/send", expect="docsend-vendor@example.com"
    )
    pret_iso = await ac.post(f"/api/v1/purchasing/returns/{pret_id}/send", headers=beta)
    assert pret_iso.status_code == 404, pret_iso.text

    approved = await ac.post(
        f"/api/v1/purchasing/invoices/{bill_id}/approve", headers=admin, json={}
    )
    assert approved.status_code == 200, approved.text
    spay = await ac.post(
        f"/api/v1/suppliers/{supplier_id}/payments",
        headers=admin,
        json={
            "supplier_id": supplier_id,
            "purchase_invoice_id": bill_id,
            "amount": 2,
            "payment_method": "cash",
        },
    )
    assert spay.status_code == 200, spay.text
    await send_ok(
        f"/api/v1/purchasing/payments/{spay.json()['data']['id']}/send",
        expect="docsend-vendor@example.com",
        product=False,
    )

    silent_po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=admin,
        json={
            "supplier_id": silent_supplier_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 4}],
        },
    )
    assert silent_po.status_code == 200, silent_po.text
    silent_issued = await ac.post(
        f"/api/v1/purchasing/orders/{silent_po.json()['data']['id']}/issue", headers=admin
    )
    assert silent_issued.status_code == 200, silent_issued.text
    silent_grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=admin,
        json={
            "purchase_order_id": silent_po.json()["data"]["id"],
            "items": [
                {
                    "po_item_id": silent_issued.json()["data"]["items"][0]["id"],
                    "received_qty": 1,
                    "accepted_qty": 1,
                }
            ],
        },
    )
    assert silent_grn.status_code == 200, silent_grn.text
    silent_grn_miss = await ac.post(
        f"/api/v1/purchasing/grn/{silent_grn.json()['data']['id']}/send", headers=admin
    )
    assert silent_grn_miss.status_code == 400, silent_grn_miss.text


@pytest.mark.asyncio
async def test_inventory_officer_sends_grn(client, db_session, seeded, monkeypatch):
    ac, seed = client
    admin = await _super(ac, seed)
    await _brand_tenant(db_session, seed)
    _enable_console_email(monkeypatch)
    user = m.User(
        tenant_id=seed["t1"].id,
        email="io-docsend@alpha.example.com",
        full_name="IO Docsend",
        password_hash=hash_password("SecurePass123!"),
        role="inventory_officer",
        email_verified=True,
        permissions=permissions_for_role("inventory_officer"),
        totp_enabled=False,
    )
    db_session.add(user)
    await db_session.commit()
    io = await auth_headers(ac, email="io-docsend@alpha.example.com", tenant_slug="alpha")

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "IO Docsend Vendor", "email": "io-vendor@example.com"},
    )
    assert supplier.status_code == 200, supplier.text
    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=admin,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 4}],
        },
    )
    assert po.status_code == 200, po.text
    issued = await ac.post(
        f"/api/v1/purchasing/orders/{po.json()['data']['id']}/issue", headers=admin
    )
    assert issued.status_code == 200, issued.text
    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=io,
        json={
            "purchase_order_id": po.json()["data"]["id"],
            "items": [
                {
                    "po_item_id": issued.json()["data"]["items"][0]["id"],
                    "received_qty": 1,
                    "accepted_qty": 1,
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    sent = await ac.post(
        f"/api/v1/purchasing/grn/{grn.json()['data']['id']}/send", headers=io
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["data"]["delivery"]["to"] == "io-vendor@example.com"
    out = get_dev_outbox()
    assert out and "Alpha Widget" in (out[-1]["html_body"] + out[-1]["text_body"])


@pytest.mark.asyncio
async def test_expense_print_letterhead(client, db_session, seeded):
    ac, seed = client
    admin = await _super(ac, seed)
    await _brand_tenant(db_session, seed)
    cats = await ac.get("/api/v1/expenses/categories", headers=admin)
    assert cats.status_code == 200, cats.text
    if cats.json()["data"]:
        cat_id = cats.json()["data"][0]["id"]
    else:
        created_cat = await ac.post(
            "/api/v1/expenses/categories",
            headers=admin,
            json={"code": "SUP", "name": "Supplies", "budget_amount": 1000},
        )
        assert created_cat.status_code == 200, created_cat.text
        cat_id = created_cat.json()["data"]["id"]
    created = await ac.post(
        "/api/v1/expenses",
        headers=admin,
        json={
            "category_id": cat_id,
            "amount": 12.5,
            "description": "Shop supplies",
            "payee": "Walk-in stationer",
            "payment_method": "cash",
        },
    )
    assert created.status_code == 200, created.text
    eid = created.json()["data"]["id"]
    printed = await ac.get(f"/api/v1/expenses/{eid}/print", headers=admin)
    assert printed.status_code == 200, printed.text
    html = printed.text
    assert "doc-company" in html
    assert "Alpha Co" in html
    assert "accounts@alpha.example.com" in html
    assert "Expense" in html
    assert "Walk-in stationer" in html
    assert "Shop supplies" in html
    assert "invented@" not in html
    pdf = await ac.get(f"/api/v1/expenses/{eid}/print?format=pdf", headers=admin)
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers.get("content-type", "").startswith("application/pdf")
    pdf_text = _pdf_text(pdf.content)
    assert pdf_text.index("Alpha Co") < pdf_text.index("EXPENSE")
    bad = await ac.get(f"/api/v1/expenses/{eid}/print?format=docx", headers=admin)
    assert bad.status_code == 422
    beta_admin = m.User(
        tenant_id=seed["t2"].id,
        email="docsend-exp@beta.example.com",
        full_name="Beta Expense Admin",
        password_hash=hash_password("SecurePass123!"),
        role="company_admin",
        email_verified=True,
        permissions=permissions_for_role("company_admin"),
        totp_enabled=False,
    )
    db_session.add(beta_admin)
    await db_session.commit()
    beta = await auth_headers(ac, email="docsend-exp@beta.example.com", tenant_slug="beta")
    isolated = await ac.get(f"/api/v1/expenses/{eid}/print", headers=beta)
    assert isolated.status_code == 404, isolated.text
