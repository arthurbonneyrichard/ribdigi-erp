"""Stage 22 P1: AR/AP aging, payments, overdue + financial export (BR-10.4–10.6)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app.credit import AGING_BUCKETS
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_ar_ap_aging_payments_overdue_and_export(client, db_session):
    """BR-10.4–10.6: AR/AP auto + aging + partial pay + due notify + PDF/Excel export."""
    ac, seed = client
    headers = await _mgr(ac)
    super_h = await _super(ac, seed)
    tenant_id = seed["t1"].id
    now = datetime.utcnow()

    # --- BR-10.4 AR: auto from sales invoice ---
    customer = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "P1 AR Customer", "credit_limit": 5000},
    )
    assert customer.status_code == 200, customer.text
    customer_id = customer.json()["data"]["id"]

    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 2,
                    "unit_price": 100,
                    "tax_rate": 0,
                }
            ],
        },
    )
    assert inv.status_code == 200, inv.text
    invoice_id = inv.json()["data"]["id"]
    inv_total = float(inv.json()["data"]["total_amount"])
    assert inv_total == pytest.approx(200)

    posted = await ac.post(
        f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers
    )
    assert posted.status_code == 200, posted.text

    journals = await ac.get("/api/v1/accounting/journal-entries", headers=headers)
    assert journals.status_code == 200
    ar_jes = [
        j
        for j in journals.json()["data"]
        if j.get("source_type") == "sales_invoice" and j.get("source_id") == invoice_id
    ]
    assert len(ar_jes) == 1

    # Age into 31–60 bucket + overdue notify horizon
    row = await db_session.get(m.SalesInvoice, invoice_id)
    row.due_date = now - timedelta(days=45)
    row.posted_at = now - timedelta(days=45)
    await db_session.commit()

    # Extra AR doc in 90+ for bucket surface
    db_session.add(
        m.SalesInvoice(
            tenant_id=tenant_id,
            invoice_number="INV-P1-AGE-90",
            customer_id=customer_id,
            status="posted",
            subtotal=50,
            tax_amount=0,
            total_amount=50,
            paid_amount=0,
            due_date=now - timedelta(days=100),
            posted_at=now - timedelta(days=100),
            created_by=seed["mgr1"].id,
        )
    )
    await db_session.commit()

    aging_ar = await ac.get(
        "/api/v1/credit/aging?kind=receivable", headers=headers
    )
    assert aging_ar.status_code == 200, aging_ar.text
    ar_data = aging_ar.json()["data"]
    assert ar_data["kind"] == "receivable"
    for key in AGING_BUCKETS:
        assert key in ar_data["totals"]
    assert float(ar_data["totals"]["31_60"]) >= 200
    assert float(ar_data["totals"]["90_plus"]) >= 50
    assert float(ar_data["total_due"]) >= 250
    assert any(d["id"] == invoice_id for d in ar_data["documents"])

    # Partial payment
    part = await ac.post(
        "/api/v1/sales/payments",
        headers=headers,
        json={
            "customer_id": customer_id,
            "amount": 75,
            "sales_invoice_id": invoice_id,
            "payment_method": "cash",
            "reference": "P1-AR-PARTIAL",
        },
    )
    assert part.status_code == 200, part.text
    inv_after = await ac.get(f"/api/v1/sales/invoices/{invoice_id}", headers=headers)
    assert inv_after.status_code == 200
    assert float(inv_after.json()["data"]["paid_amount"]) == pytest.approx(75)
    assert inv_after.json()["data"]["status"] in {"partial", "posted"}

    # Overdue / payment-due notification (AR)
    scan = await ac.post("/api/v1/notifications/scan-due", headers=headers)
    assert scan.status_code == 200, scan.text
    assert int(scan.json()["data"]["payment_due"]) >= 1
    notes = await ac.get("/api/v1/notifications", headers=headers)
    assert any(
        n.get("category") == "payment_due" and n.get("entity_id") == invoice_id
        for n in notes.json()["data"]
    )

    # --- BR-10.5 AP: auto from purchase / GRN → PI ---
    product = seed["p1"]
    product.stock_qty = float(product.stock_qty or 0)
    await db_session.commit()

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "P1 AP Vendor"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [
                {
                    "product_id": str(product.id),
                    "quantity": 4,
                    "unit_price": 25,
                    "tax_rate": 0,
                }
            ],
        },
    )
    assert po.status_code == 200, po.text
    po_id = po.json()["data"]["id"]
    po_item_id = po.json()["data"]["items"][0]["id"]
    assert float(po.json()["data"]["total_amount"]) == pytest.approx(100)

    sent = await ac.post(f"/api/v1/purchasing/orders/{po_id}/send", headers=headers)
    assert sent.status_code == 200, sent.text

    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=headers,
        json={
            "purchase_order_id": po_id,
            "items": [
                {
                    "po_item_id": po_item_id,
                    "received_qty": 4,
                    "accepted_qty": 4,
                    "rejected_qty": 0,
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    grn_id = grn.json()["data"]["id"]

    # AP recognized on GRN journal
    journals2 = await ac.get("/api/v1/accounting/journal-entries", headers=headers)
    grn_jes = [
        j
        for j in journals2.json()["data"]
        if j.get("source_type") == "grn" and j.get("source_id") == grn_id
    ]
    assert len(grn_jes) == 1

    pi = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={"goods_receipt_id": grn_id},
    )
    assert pi.status_code == 200, pi.text
    pi_id = pi.json()["data"]["id"]
    approved = await ac.post(
        f"/api/v1/purchasing/invoices/{pi_id}/approve", headers=headers
    )
    assert approved.status_code == 200, approved.text

    bill = await db_session.get(m.PurchaseInvoice, pi_id)
    bill.due_date = now - timedelta(days=2)
    bill.status = "unpaid"
    await db_session.commit()

    aging_ap = await ac.get("/api/v1/credit/aging?kind=payable", headers=headers)
    assert aging_ap.status_code == 200, aging_ap.text
    ap_data = aging_ap.json()["data"]
    assert ap_data["kind"] == "payable"
    for key in AGING_BUCKETS:
        assert key in ap_data["totals"]
    assert float(ap_data["total_due"]) >= 100
    assert any(
        d.get("id") == pi_id or d.get("id") == po_id for d in ap_data["documents"]
    )

    # Partial AP payment against bill
    ap_part = await ac.post(
        f"/api/v1/suppliers/{supplier_id}/payments",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "amount": 40,
            "purchase_invoice_id": pi_id,
            "payment_method": "bank_transfer",
            "reference": "P1-AP-PARTIAL",
        },
    )
    assert ap_part.status_code == 200, ap_part.text
    bill2 = (
        await db_session.execute(
            select(m.PurchaseInvoice).where(m.PurchaseInvoice.id == pi_id)
        )
    ).scalar_one()
    await db_session.refresh(bill2)
    assert float(bill2.paid_amount or 0) == pytest.approx(40)
    assert bill2.status in {"partial", "unpaid", "overdue"}

    # Due date notification for AP bill
    scan2 = await ac.post("/api/v1/notifications/scan-due", headers=headers)
    assert scan2.status_code == 200, scan2.text
    notes2 = await ac.get("/api/v1/notifications", headers=headers)
    assert any(
        n.get("category") == "payment_due"
        and n.get("entity_id") == pi_id
        and n.get("entity_type") == "purchase_invoice"
        for n in notes2.json()["data"]
    ), notes2.json()["data"]

    # Supplier payment schedule (due visibility)
    schedule = await ac.get(
        f"/api/v1/suppliers/{supplier_id}/payment-schedule", headers=headers
    )
    assert schedule.status_code == 200, schedule.text

    # --- BR-10.6 financial export PDF + Excel (P&L / TB) ---
    for report_type in ("profit_loss", "trial_balance"):
        pdf = await ac.get(
            "/api/v1/reports/export",
            headers=super_h,
            params={"report_type": report_type, "format": "pdf"},
        )
        assert pdf.status_code == 200, pdf.text
        assert "application/pdf" in pdf.headers.get("content-type", "")
        assert pdf.content.startswith(b"%PDF")

        xlsx = await ac.get(
            "/api/v1/reports/export",
            headers=super_h,
            params={"report_type": report_type, "format": "xlsx"},
        )
        assert xlsx.status_code == 200, xlsx.text
        assert "spreadsheetml" in xlsx.headers.get("content-type", "")
        assert xlsx.content[:2] == b"PK"


def test_br_10_4_10_5_10_6_and_plan_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    s104 = br.split("#### BR-10.4 Accounts Receivable (AR)")[1].split("#### BR-10.5")[0]
    assert "[x] Auto-generation from sales invoices" in s104
    assert "[x] Customer aging report" in s104
    assert "[x] Payment recording against invoices" in s104
    assert "[x] Partial payment support" in s104
    assert "[x] Overdue notification automation" in s104
    assert "Stage 22 P1" in s104
    assert "test_ar_ap_export_p1.py" in s104

    s105 = br.split("#### BR-10.5 Accounts Payable (AP)")[1].split("#### BR-10.6")[0]
    assert "[x] Auto-generation from purchase invoices" in s105
    assert "[x] Supplier aging report" in s105
    assert "[x] Payment recording against bills" in s105
    assert "[x] Partial payment support" in s105
    assert "[x] Due date notifications" in s105
    assert "Stage 22 P1" in s105

    s106 = br.split("#### BR-10.6 Financial Reports")[1].split("---")[0]
    assert "[x] **Profit & Loss:**" in s106
    assert "[x] **Cash Flow:**" in s106
    assert "[x] **Trial Balance:**" in s106
    assert "[x] Export to PDF and Excel" in s106
    assert "Stage 22 P1" in s106

    plan = (ROOT / "docs" / "STAGE_22_PLAN.md").read_text(encoding="utf-8")
    p1_line = [ln for ln in plan.splitlines() if "| **P1**" in ln][0]
    assert "COMPLETE" in p1_line
    assert "test_ar_ap_export_p1.py" in plan
