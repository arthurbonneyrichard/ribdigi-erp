"""Stage 18 S1: tenant isolation matrix completeness for launch-smoke surfaces."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app import api_keys as api_keys_svc
from app import expenses as expenses_svc
from app import models as m
from app import purchasing as purchasing_svc
from app import stock_counts as stock_counts_svc
from app import webhooks as webhooks_svc
from tests.conftest import auth_headers

pytestmark = pytest.mark.isolation

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_foreign_expense_and_pi_ocr_apply_404(client, db_session):
    """OCR-apply mirrors OCR-suggest: cross-tenant resource → 404."""
    ac, seed = client
    await expenses_svc.ensure_default_categories(db_session, seed["t2"].id)
    await db_session.commit()
    from sqlalchemy import select

    cats = (
        await db_session.execute(
            select(m.ExpenseCategory).where(m.ExpenseCategory.tenant_id == seed["t2"].id)
        )
    ).scalars().all()
    expense = await expenses_svc.create_expense(
        db_session,
        tenant_id=seed["t2"].id,
        user_id=seed["u2"].id,
        amount=22,
        description="Beta OCR apply expense",
        category_id=cats[0].id if cats else None,
        payment_method="cash",
    )
    expense.attachment_url = f"{seed['t2'].id}/expenses/beta-apply.pdf"
    inv = await purchasing_svc.create_purchase_invoice(
        db_session,
        tenant_id=seed["t2"].id,
        user_id=seed["u2"].id,
        supplier_id=seed["supplier2"].id,
        items=[{"product_id": seed["p2"].id, "quantity": 1, "unit_price": 3}],
    )
    inv.attachment_url = f"{seed['t2'].id}/purchase_invoices/beta-apply.pdf"
    await db_session.commit()

    headers = await _mgr(ac)
    exp_r = await ac.post(
        f"/api/v1/expenses/{expense.id}/ocr-apply",
        headers=headers,
        json={"confirm": True, "amount": 22, "description": "x"},
    )
    assert exp_r.status_code == 404

    super_h = await _super(ac, seed)
    pi_r = await ac.post(
        f"/api/v1/purchasing/invoices/{inv.id}/ocr-apply",
        headers=super_h,
        json={"confirm": True, "supplier_invoice_number": "X", "notes": "x"},
    )
    assert pi_r.status_code == 404


@pytest.mark.asyncio
async def test_foreign_api_key_get_usage_delete_404(client, db_session):
    ac, seed = client
    row, _raw = await api_keys_svc.create_key(
        db_session,
        tenant_id=seed["t2"].id,
        user_id=seed["u2"].id,
        name="Beta integrator",
        permissions={"inventory": ["read"]},
    )
    await db_session.commit()
    key_id = row.id

    headers = await _super(ac, seed)
    assert (await ac.get(f"/api/v1/api-keys/{key_id}", headers=headers)).status_code == 404
    assert (await ac.get(f"/api/v1/api-keys/{key_id}/usage", headers=headers)).status_code == 404
    assert (await ac.delete(f"/api/v1/api-keys/{key_id}", headers=headers)).status_code == 404

    listed = await ac.get("/api/v1/api-keys", headers=headers)
    assert listed.status_code == 200
    assert all(r["id"] != key_id for r in listed.json()["data"])


@pytest.mark.asyncio
async def test_foreign_webhook_get_delete_test_404(client, db_session):
    ac, seed = client
    row, _secret = await webhooks_svc.create_endpoint(
        db_session,
        tenant_id=seed["t2"].id,
        user_id=seed["u2"].id,
        url="https://hooks.beta.example.com/ribdigi",
        events=["sale.created"],
        description="Beta hook",
    )
    await db_session.commit()
    webhook_id = row.id

    headers = await _super(ac, seed)
    assert (await ac.get(f"/api/v1/webhooks/{webhook_id}", headers=headers)).status_code == 404
    assert (await ac.delete(f"/api/v1/webhooks/{webhook_id}", headers=headers)).status_code == 404
    assert (
        await ac.post(f"/api/v1/webhooks/{webhook_id}/test", headers=headers)
    ).status_code == 404

    listed = await ac.get("/api/v1/webhooks", headers=headers)
    assert listed.status_code == 200
    assert all(r["id"] != webhook_id for r in listed.json()["data"])


@pytest.mark.asyncio
async def test_foreign_stock_count_and_warehouse_transfer_404(client, db_session):
    ac, seed = client
    tenant_id = seed["t2"].id
    wh_a = m.Warehouse(tenant_id=tenant_id, name="Beta Count WH", code="B-CNT")
    wh_b = m.Warehouse(tenant_id=tenant_id, name="Beta Xfer WH", code="B-XFR")
    db_session.add_all([wh_a, wh_b])
    await db_session.flush()

    count = await stock_counts_svc.create_count(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["u2"].id,
        warehouse_id=wh_a.id,
        notes="Beta count",
    )
    transfer = m.StockTransfer(
        tenant_id=tenant_id,
        transfer_number="TR-BETA-S18",
        from_warehouse_id=wh_a.id,
        to_warehouse_id=wh_b.id,
        status="draft",
        created_by=seed["u2"].id,
    )
    db_session.add(transfer)
    await db_session.commit()
    count_id, transfer_id = count.id, transfer.id

    headers = await _mgr(ac)
    assert (await ac.get(f"/api/v1/inventory/stock-counts/{count_id}", headers=headers)).status_code == 404
    assert (
        await ac.post(f"/api/v1/inventory/stock-counts/{count_id}/complete", headers=headers)
    ).status_code == 404
    assert (
        await ac.get(f"/api/v1/inventory/stock-transfers/{transfer_id}", headers=headers)
    ).status_code == 404
    assert (
        await ac.post(f"/api/v1/inventory/stock-transfers/{transfer_id}/ship", headers=headers)
    ).status_code == 404

    counts = await ac.get("/api/v1/inventory/stock-counts", headers=headers)
    assert counts.status_code == 200
    assert all(r["id"] != count_id for r in counts.json()["data"])

    xfers = await ac.get("/api/v1/inventory/stock-transfers", headers=headers)
    assert xfers.status_code == 200
    assert all(r.get("transfer_number") != "TR-BETA-S18" for r in xfers.json()["data"])


@pytest.mark.asyncio
async def test_foreign_quotation_order_and_product_surfaces_404(client, db_session):
    ac, seed = client
    tenant_id = seed["t2"].id
    quote = m.SalesQuotation(
        tenant_id=tenant_id,
        quotation_number="Q-BETA-S18",
        customer_id=seed["party2"].id,
        status="draft",
        subtotal=10,
        total_amount=10,
        created_by=seed["u2"].id,
    )
    order = m.SalesOrder(
        tenant_id=tenant_id,
        order_number="SO-BETA-S18",
        customer_id=seed["party2"].id,
        status="draft",
        subtotal=10,
        total_amount=10,
        created_by=seed["u2"].id,
    )
    db_session.add_all([quote, order])
    await db_session.commit()

    headers = await _mgr(ac)
    assert (await ac.get(f"/api/v1/sales/quotations/{quote.id}", headers=headers)).status_code == 404
    assert (await ac.get(f"/api/v1/sales/orders/{order.id}", headers=headers)).status_code == 404
    assert (await ac.get(f"/api/v1/products/{seed['p2'].id}", headers=headers)).status_code == 404
    assert (
        await ac.get(f"/api/v1/products/{seed['p2'].id}/warehouse-stock", headers=headers)
    ).status_code == 404

    reorder = await ac.post(
        "/api/v1/inventory/low-stock/reorder-po",
        headers=headers,
        json={"product_id": seed["p2"].id, "supplier_id": seed["supplier2"].id},
    )
    assert reorder.status_code == 404


@pytest.mark.asyncio
async def test_mismatched_tenant_header_on_api_keys_and_webhooks(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    bad = {**headers, "X-Tenant-ID": seed["t2"].id}

    keys = await ac.get("/api/v1/api-keys", headers=bad)
    assert keys.status_code == 403

    hooks = await ac.get("/api/v1/webhooks", headers=bad)
    assert hooks.status_code == 403


def test_isolation_matrix_s1_docs():
    plan = (ROOT / "docs/STAGE_18_PLAN.md").read_text(encoding="utf-8")
    assert "| **S1**" in plan
    assert "test_isolation_matrix_s1.py" in plan
    assert "COMPLETE" in plan
    pr = (ROOT / "PRODUCTION_READINESS.md").read_text(encoding="utf-8")
    assert "Stage 18 S1" in pr
    assert "test_isolation_matrix_s1.py" in pr
    sec = (ROOT / "docs/SECURITY_GUIDE.md").read_text(encoding="utf-8")
    assert "Stage 18 S1" in sec or "isolation matrix" in sec.lower()
