"""AR collection schedule — overdue buckets, aging visibility, export, RBAC."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pyotp
import pytest

from app import accounting as accounting_svc
from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_customer_collection_schedule_buckets_and_overdue_aging(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    seed["t1"].early_pay_discount_pct = 2
    seed["t1"].early_pay_discount_days = 10

    company_id = seed["c1"].id
    customer = m.Party(
        tenant_id=tenant_id,
        company_id=company_id,
        name="AR Collect Customer",
        kind="customer",
        credit_limit=1000,
        balance=350,
    )
    db_session.add(customer)
    await db_session.flush()

    now = datetime.utcnow()
    overdue = m.SalesInvoice(
        tenant_id=tenant_id,
        company_id=company_id,
        invoice_number="INV-COLL-OVER",
        customer_id=customer.id,
        status="overdue",
        subtotal=100,
        tax_amount=0,
        total_amount=100,
        paid_amount=0,
        due_date=now - timedelta(days=5),
        posted_at=now - timedelta(days=35),
        created_by=seed["admin1"].id,
    )
    sent_open = m.SalesInvoice(
        tenant_id=tenant_id,
        company_id=company_id,
        invoice_number="INV-COLL-SENT",
        customer_id=customer.id,
        status="sent",
        subtotal=80,
        tax_amount=0,
        total_amount=80,
        paid_amount=0,
        due_date=now + timedelta(days=4),
        posted_at=now - timedelta(days=2),
        created_by=seed["admin1"].id,
    )
    upcoming = m.SalesInvoice(
        tenant_id=tenant_id,
        company_id=company_id,
        invoice_number="INV-COLL-UP",
        customer_id=customer.id,
        status="posted",
        subtotal=170,
        tax_amount=0,
        total_amount=170,
        paid_amount=0,
        due_date=now + timedelta(days=7),
        posted_at=now - timedelta(days=1),
        created_by=seed["admin1"].id,
    )
    paid = m.SalesInvoice(
        tenant_id=tenant_id,
        company_id=company_id,
        invoice_number="INV-COLL-PAID",
        customer_id=customer.id,
        status="paid",
        subtotal=40,
        tax_amount=0,
        total_amount=40,
        paid_amount=40,
        due_date=now - timedelta(days=2),
        posted_at=now - timedelta(days=10),
        created_by=seed["admin1"].id,
    )
    db_session.add_all([overdue, sent_open, upcoming, paid])
    await db_session.commit()

    r = await ac.get(
        f"/api/v1/customers/{customer.id}/collection-schedule", headers=headers
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["customer_id"] == customer.id
    assert body["customer_name"] == "AR Collect Customer"
    assert body["total_due"] == 350.0
    assert body["overdue_total"] == 100.0
    assert body["upcoming_total"] == 250.0
    numbers = [item["invoice_number"] for item in body["items"]]
    assert numbers[0] == "INV-COLL-OVER"
    assert "INV-COLL-PAID" not in numbers
    assert body["items"][0]["schedule_bucket"] == "overdue"
    assert body["items"][0]["is_overdue"] is True
    assert body["items"][0]["status"] == "overdue"
    assert body["items"][0]["days_overdue"] == 5
    sent = next(i for i in body["items"] if i["invoice_number"] == "INV-COLL-SENT")
    assert sent["schedule_bucket"] == "upcoming"
    assert sent["status"] == "sent"
    assert sent["early_discount"]["eligible"] is True
    assert sent["early_discount"]["discount_amount"] == 1.6

    aging = await ac.get("/api/v1/credit/aging?kind=receivable", headers=headers)
    assert aging.status_code == 200, aging.text
    aging_body = aging.json()["data"]
    aging_nums = {d["document_number"] for d in aging_body["documents"]}
    assert "INV-COLL-OVER" in aging_nums
    assert "INV-COLL-SENT" in aging_nums
    assert "INV-COLL-UP" in aging_nums
    assert "INV-COLL-PAID" not in aging_nums
    assert float(aging_body["overdue_total"]) >= 100.0

    stmt = await ac.get(
        f"/api/v1/credit/customers/{customer.id}/statement", headers=headers
    )
    assert stmt.status_code == 200, stmt.text
    lines = {ln["reference"]: ln for ln in stmt.json()["data"]["lines"]}
    assert float(lines["INV-COLL-OVER"]["balance_due"]) == 100.0
    assert float(lines["INV-COLL-SENT"]["balance_due"]) == 80.0
    assert float(lines["INV-COLL-PAID"]["balance_due"]) == 0.0


@pytest.mark.asyncio
async def test_customer_collection_schedule_export_bucket_filter(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    company_id = seed["c1"].id
    customer = m.Party(
        tenant_id=tenant_id,
        company_id=company_id,
        name="AR Export Customer",
        kind="customer",
        credit_limit=500,
        balance=180,
    )
    db_session.add(customer)
    await db_session.flush()
    now = datetime.utcnow()
    db_session.add_all(
        [
            m.SalesInvoice(
                tenant_id=tenant_id,
                company_id=company_id,
                invoice_number="INV-CEXP-OVER",
                customer_id=customer.id,
                status="overdue",
                subtotal=60,
                tax_amount=0,
                total_amount=60,
                paid_amount=0,
                due_date=now - timedelta(days=8),
                posted_at=now - timedelta(days=40),
                created_by=seed["admin1"].id,
            ),
            m.SalesInvoice(
                tenant_id=tenant_id,
                company_id=company_id,
                invoice_number="INV-CEXP-UP",
                customer_id=customer.id,
                status="posted",
                subtotal=120,
                tax_amount=0,
                total_amount=120,
                paid_amount=0,
                due_date=now + timedelta(days=6),
                posted_at=now,
                created_by=seed["admin1"].id,
            ),
        ]
    )
    await db_session.commit()

    exported = await ac.get(
        f"/api/v1/customers/{customer.id}/collection-schedule/export", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "schedule_bucket" in header
    assert "days_overdue" in header
    assert "INV-CEXP-OVER" in text and "INV-CEXP-UP" in text

    overdue_only = await ac.get(
        f"/api/v1/customers/{customer.id}/collection-schedule/export?schedule_bucket=overdue",
        headers=headers,
    )
    assert overdue_only.status_code == 200, overdue_only.text
    assert "INV-CEXP-OVER" in overdue_only.text
    assert "INV-CEXP-UP" not in overdue_only.text

    bad = await ac.get(
        f"/api/v1/customers/{customer.id}/collection-schedule/export?schedule_bucket=never",
        headers=headers,
    )
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_customer_collection_schedule_rbac_and_not_found(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    customer = m.Party(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        name="AR RBAC",
        kind="customer",
        credit_limit=0,
    )
    db_session.add(customer)
    await db_session.commit()

    missing = await ac.get(
        "/api/v1/customers/00000000-0000-0000-0000-000000000099/collection-schedule",
        headers=headers,
    )
    assert missing.status_code == 404

    isolated = await ac.get(
        f"/api/v1/customers/{customer.id}/collection-schedule",
        headers={**headers, "X-Tenant-ID": seed["t2"].id},
    )
    assert isolated.status_code == 403

    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    denied = await ac.get(
        f"/api/v1/customers/{customer.id}/collection-schedule", headers=cashier
    )
    assert denied.status_code == 403


def test_credit_ui_collection_schedule_c1():
    api_src = Path(__file__).resolve().parents[1] / "app" / "api.py"
    assert "/customers/{customer_id}/collection-schedule" in api_src.read_text(
        encoding="utf-8"
    )
    export_src = Path(__file__).resolve().parents[1] / "app" / "credit_ops_export.py"
    assert "export_customer_collection_schedule_csv" in export_src.read_text(
        encoding="utf-8"
    )
    page_path = ROOT / "frontend/app/credit/page.tsx"
    if not page_path.is_file():
        pytest.skip("frontend tree not mounted in this test environment")
    page = page_path.read_text(encoding="utf-8")
    assert "/customers/${partyId}/collection-schedule" in page
    assert "/collection-schedule/export" in page
    assert "Collection schedule" in page
    assert 'id="payment-schedule"' in page
    assert "/payment-schedule/export" in page
