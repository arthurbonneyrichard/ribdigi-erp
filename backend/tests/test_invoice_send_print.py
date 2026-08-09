"""BR-7.4 sales invoice print templates, email send, and overdue status."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app import models as m
from app.emailer import clear_dev_outbox, get_dev_outbox
from app.sales import render_invoice_text
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _admin(ac):
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


def test_render_invoice_text_templates():
    data = {
        "invoice_number": "INV-34535",
        "status": "posted",
        "due_date": "2026-08-01",
        "subtotal": 10,
        "tax_amount": 0,
        "discount_amount": 0,
        "total_amount": 10,
        "paid_amount": 0,
        "balance_due": 10,
        "items": [{"product_id": "p1", "quantity": 2, "line_total": 10}],
    }
    a4 = render_invoice_text(data, company_name="Alpha Co", customer_name="Buyer", template="a4")
    t80 = render_invoice_text(
        data, company_name="Alpha Co", customer_name="Buyer", template="thermal_80"
    )
    t58 = render_invoice_text(
        data, company_name="Alpha Co", customer_name="Buyer", template="thermal_58"
    )
    assert "INV-34535" in a4 and "Alpha Co" in a4 and "TOTAL:" in a4
    assert "Thank you!" in t80 and "Thank you!" in t58
    assert len(t58.splitlines()[0]) <= 32 or t58.splitlines()[0] == "Alpha Co"


@pytest.mark.asyncio
async def test_invoice_print_send_overdue_and_no_repost(client, db_session, monkeypatch):
    ac, seed = client
    headers = await _mgr(ac)
    admin = await _admin(ac)
    clear_dev_outbox()
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={
            "name": "Invoice Mail Buyer",
            "email": "invoice-buyer@example.com",
            "payment_terms_days": 7,
            "credit_limit": 5000,
        },
    )
    assert cust.status_code == 200, cust.text
    customer_id = cust.json()["data"]["id"]

    tpl = await ac.patch(
        "/api/v1/tenants/me",
        headers=admin,
        json={"invoice_print_template": "thermal_80"},
    )
    assert tpl.status_code == 200, tpl.text
    assert tpl.json()["data"]["invoice_print_template"] == "thermal_80"

    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 8}],
        },
    )
    assert inv.status_code == 200, inv.text
    invoice_id = inv.json()["data"]["id"]
    invoice_number = inv.json()["data"]["invoice_number"]

    posted = await ac.post(f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers)
    assert posted.status_code == 200, posted.text
    assert posted.json()["data"]["status"] == "posted"

    await db_session.expire_all()
    product_before = (
        await db_session.execute(select(m.Product).where(m.Product.id == seed["p1"].id))
    ).scalar_one()
    stock_before = float(product_before.stock_qty)

    printed_default = await ac.get(f"/api/v1/sales/invoices/{invoice_id}/print", headers=headers)
    assert printed_default.status_code == 200, printed_default.text
    body = printed_default.json()["data"]
    assert body["template"] == "thermal_80"
    assert invoice_number in body["text"]
    assert "Alpha Co" in body["text"]
    assert "Invoice Mail Buyer" in body["text"]

    printed_a4 = await ac.get(
        f"/api/v1/sales/invoices/{invoice_id}/print",
        headers=headers,
        params={"template": "a4"},
    )
    assert printed_a4.status_code == 200, printed_a4.text
    assert printed_a4.json()["data"]["template"] == "a4"

    bad_tpl = await ac.get(
        f"/api/v1/sales/invoices/{invoice_id}/print",
        headers=headers,
        params={"template": "poster"},
    )
    assert bad_tpl.status_code == 400

    sent = await ac.post(f"/api/v1/sales/invoices/{invoice_id}/send", headers=headers)
    assert sent.status_code == 200, sent.text
    data = sent.json()["data"]
    assert data["status"] == "sent"
    assert data["emailed_to"] == "invoice-buyer@example.com"
    assert data["emailed_at"]
    assert data["delivery"]["mode"] == "console"
    out = get_dev_outbox()
    assert out and invoice_number in out[0]["subject"]

    await db_session.expire_all()
    product_after = (
        await db_session.execute(select(m.Product).where(m.Product.id == seed["p1"].id))
    ).scalar_one()
    assert float(product_after.stock_qty) == stock_before

    journals = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.tenant_id == seed["t1"].id,
                m.JournalEntry.source_type == "sales_invoice",
                m.JournalEntry.source_id == invoice_id,
            )
        )
    ).scalars().all()
    assert len(journals) == 1

    row = (
        await db_session.execute(select(m.SalesInvoice).where(m.SalesInvoice.id == invoice_id))
    ).scalar_one()
    row.due_date = datetime.utcnow() - timedelta(days=3)
    await db_session.commit()

    got = await ac.get(f"/api/v1/sales/invoices/{invoice_id}", headers=headers)
    assert got.status_code == 200, got.text
    overdue = got.json()["data"]
    assert overdue["status"] == "overdue"
    assert overdue["is_overdue"] is True

    resend = await ac.post(
        f"/api/v1/sales/invoices/{invoice_id}/send",
        headers=headers,
        json={"to": "override@example.com"},
    )
    assert resend.status_code == 200, resend.text
    assert resend.json()["data"]["status"] == "overdue"
    assert resend.json()["data"]["emailed_to"] == "override@example.com"


@pytest.mark.asyncio
async def test_invoice_send_requires_email_and_blocks_draft(client, monkeypatch):
    ac, seed = client
    headers = await _mgr(ac)
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "No Email Buyer", "credit_limit": 1000},
    )
    customer_id = cust.json()["data"]["id"]
    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 2}],
        },
    )
    invoice_id = inv.json()["data"]["id"]

    draft_send = await ac.post(f"/api/v1/sales/invoices/{invoice_id}/send", headers=headers)
    assert draft_send.status_code == 409

    posted = await ac.post(f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers)
    assert posted.status_code == 200, posted.text
    no_email = await ac.post(f"/api/v1/sales/invoices/{invoice_id}/send", headers=headers)
    assert no_email.status_code == 400


@pytest.mark.asyncio
async def test_foreign_invoice_print_and_send_404(client, db_session, monkeypatch):
    ac, seed = client
    headers = await _mgr(ac)
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")

    foreign_id = seed["inv2"].id
    printed = await ac.get(f"/api/v1/sales/invoices/{foreign_id}/print", headers=headers)
    assert printed.status_code == 404
    sent = await ac.post(f"/api/v1/sales/invoices/{foreign_id}/send", headers=headers)
    assert sent.status_code == 404
