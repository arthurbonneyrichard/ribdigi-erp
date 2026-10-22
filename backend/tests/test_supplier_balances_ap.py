"""Supplier balances (AP aging) from billed invoices, not unbilled POs."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app import credit as credit_svc
from app import models as m
from tests.conftest import auth_headers


def _pi(
    *,
    tenant_id: str,
    supplier_id: str,
    number: str,
    total: float,
    paid: float = 0,
    status: str = "unpaid",
    due: datetime | None = None,
    po_id: str | None = None,
    invoice_date: datetime | None = None,
) -> m.PurchaseInvoice:
    now = invoice_date or datetime.utcnow()
    return m.PurchaseInvoice(
        tenant_id=tenant_id,
        supplier_id=supplier_id,
        invoice_number=number,
        status=status,
        invoice_date=now,
        due_date=due,
        subtotal=total,
        total_amount=total,
        paid_amount=paid,
        purchase_order_id=po_id,
    )


@pytest.mark.asyncio
async def test_ap_aging_empty_no_fake_bills(db_session, seeded):
    report = await credit_svc.ap_aging(db_session, seeded["t1"].id)
    assert report["kind"] == "payable"
    assert report["total_due"] == 0
    assert report["documents"] == []
    assert report["commitments"] == []
    assert report["commitment_total"] == 0


@pytest.mark.asyncio
async def test_ap_aging_unpaid_partial_overdue_and_unbilled_po(db_session, seeded):
    t1 = seeded["t1"]
    supplier = m.Party(tenant_id=t1.id, name="Alpha Steel", kind="supplier")
    db_session.add(supplier)
    await db_session.flush()

    as_of = datetime(2026, 9, 28, 12, 0, 0)
    unpaid = _pi(
        tenant_id=t1.id,
        supplier_id=supplier.id,
        number="BILL-U",
        total=100,
        paid=0,
        status="unpaid",
        due=as_of + timedelta(days=10),
        invoice_date=as_of,
    )
    partial = _pi(
        tenant_id=t1.id,
        supplier_id=supplier.id,
        number="BILL-P",
        total=80,
        paid=30,
        status="partial",
        due=as_of + timedelta(days=5),
        invoice_date=as_of,
    )
    overdue = _pi(
        tenant_id=t1.id,
        supplier_id=supplier.id,
        number="BILL-O",
        total=40,
        paid=0,
        status="overdue",
        due=as_of - timedelta(days=12),
        invoice_date=as_of - timedelta(days=20),
    )
    po = m.PurchaseOrder(
        tenant_id=t1.id,
        supplier_id=supplier.id,
        po_number="PO-OPEN",
        status="sent",
        total_amount=500,
        paid_amount=0,
    )
    foreign = _pi(
        tenant_id=seeded["t2"].id,
        supplier_id=seeded["supplier2"].id,
        number="BILL-BETA",
        total=999,
        status="unpaid",
        due=as_of,
    )
    db_session.add_all([unpaid, partial, overdue, po, foreign])
    await db_session.commit()

    report = await credit_svc.ap_aging(db_session, t1.id, as_of=as_of)
    assert report["total_due"] == 190.0
    assert report["overdue_total"] == 40.0
    assert report["not_yet_due_total"] == 150.0
    assert report["commitment_total"] == 500.0
    nums = {d["document_number"]: d for d in report["documents"]}
    assert set(nums) == {"BILL-U", "BILL-P", "BILL-O"}
    assert nums["BILL-P"]["paid_amount"] == 30.0
    assert nums["BILL-P"]["balance_due"] == 50.0
    assert nums["BILL-P"]["total_amount"] == 80.0
    assert report["commitments"][0]["document_number"] == "PO-OPEN"
    assert all(d["document_type"] == "purchase_invoice" for d in report["documents"])


@pytest.mark.asyncio
async def test_ap_aging_posted_return_credits_open_bill(db_session, seeded):
    t1 = seeded["t1"]
    supplier = m.Party(tenant_id=t1.id, name="Return Co", kind="supplier")
    db_session.add(supplier)
    await db_session.flush()
    po = m.PurchaseOrder(
        tenant_id=t1.id,
        supplier_id=supplier.id,
        po_number="PO-RET",
        status="received",
        total_amount=200,
        paid_amount=25,
    )
    db_session.add(po)
    await db_session.flush()
    inv = _pi(
        tenant_id=t1.id,
        supplier_id=supplier.id,
        number="BILL-RET",
        total=200,
        paid=0,
        status="unpaid",
        po_id=po.id,
    )
    ret = m.PurchaseReturn(
        tenant_id=t1.id,
        supplier_id=supplier.id,
        purchase_order_id=po.id,
        goods_receipt_id=po.id,
        return_number="PR-1",
        status="posted",
        total_amount=25,
    )
    db_session.add_all([inv, ret])
    await db_session.commit()

    report = await credit_svc.ap_aging(db_session, t1.id)
    assert report["total_due"] == 175.0
    assert report["documents"][0]["balance_due"] == 175.0
    assert report["commitment_total"] == 0


@pytest.mark.asyncio
async def test_credit_aging_api_receivable_and_payable(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    rec = await ac.get("/api/v1/credit/aging?kind=receivable", headers=headers)
    assert rec.status_code == 200, rec.text
    assert rec.json()["data"]["kind"] == "receivable"

    pay = await ac.get("/api/v1/credit/aging?kind=payable", headers=headers)
    assert pay.status_code == 200, pay.text
    body = pay.json()["data"]
    assert body["kind"] == "payable"
    assert "total_due" in body
    assert "commitments" in body
    assert "overdue_total" in body
    assert "not_yet_due_total" in body

    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    denied = await ac.get("/api/v1/credit/aging?kind=payable", headers=cashier)
    assert denied.status_code == 403, denied.text


@pytest.mark.asyncio
async def test_credit_aging_api_failure_is_not_zero_success(client, monkeypatch):
    ac, _seed = client

    async def boom(*_a, **_k):
        raise HTTPException(status_code=500, detail="aging query failed")

    monkeypatch.setattr("app.api.credit_svc.ap_aging", boom)
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/credit/aging?kind=payable", headers=headers)
    assert r.status_code == 500, r.text
    data = r.json().get("data")
    assert data in (None, {}) or "total_due" not in (data or {})


def test_credit_page_error_retry_and_payable_copy():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    page = (root / "frontend/app/(dashboard)/credit/page.tsx").read_text(encoding="utf-8")
    assert "Supplier balances" in page
    assert "Retry" in page
    assert "loadState" in page
    assert "We owe" in page
    assert "commitments" in page
    assert "kind === 'payable'" in page
    assert "Receivables" in page
    assert 'aria-label="Show supplier payments"' in page
    css = (root / "frontend/app/globals.css").read_text(encoding="utf-8")
    assert ".credit-page" in css
    assert ".erp-tabs" in css
