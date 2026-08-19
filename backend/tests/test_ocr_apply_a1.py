"""Stage 10 A1: human-confirmed OCR apply endpoints (expenses + purchase invoices)."""

from __future__ import annotations

from datetime import datetime

import pytest

from app import models as m
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_expense_ocr_apply_requires_confirm(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    tenant = seed["t1"]
    tenant.expense_approval_threshold = 10
    await db_session.commit()

    created = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "category": "Supplies",
            "amount": 50,
            "description": "old",
            "payment_method": "cash",
            "payee": "old",
        },
    )
    assert created.status_code == 200, created.text
    expense_id = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "pending"

    denied = await ac.post(
        f"/api/v1/expenses/{expense_id}/ocr-apply",
        headers=headers,
        json={"payee": "Office Depot", "amount": 75.5},
    )
    assert denied.status_code == 400
    assert "confirm" in str(denied.json().get("detail", "")).lower()

    applied = await ac.post(
        f"/api/v1/expenses/{expense_id}/ocr-apply",
        headers=headers,
        json={
            "confirm": True,
            "payee": "Office Depot",
            "amount": 75.5,
            "description": "Receipt — Office Depot",
            "reference": "R-9",
            "expense_date": "2026-04-01T00:00:00",
        },
    )
    assert applied.status_code == 200, applied.text
    body = applied.json()["data"]
    assert body["payee"] == "Office Depot"
    assert float(body["amount"]) == pytest.approx(75.5)
    assert body["reference"] == "R-9"
    assert body["status"] == "pending"


@pytest.mark.asyncio
async def test_purchase_invoice_ocr_apply_draft_only(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "A1 OCR Sup"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    inv = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [
                {
                    "product_id": str(seed["p1"].id),
                    "quantity": 1,
                    "unit_price": 50,
                    "tax_rate": 0,
                }
            ],
        },
    )
    assert inv.status_code == 200, inv.text
    invoice_id = inv.json()["data"]["id"]
    assert inv.json()["data"]["status"] == "draft"

    denied = await ac.post(
        f"/api/v1/purchasing/invoices/{invoice_id}/ocr-apply",
        headers=headers,
        json={"supplier_invoice_number": "SUP-42", "notes": "From OCR"},
    )
    assert denied.status_code == 400

    applied = await ac.post(
        f"/api/v1/purchasing/invoices/{invoice_id}/ocr-apply",
        headers=headers,
        json={
            "confirm": True,
            "supplier_invoice_number": "SUP-42",
            "notes": "From OCR",
            "invoice_date": "2026-03-10T00:00:00",
        },
    )
    assert applied.status_code == 200, applied.text
    data = applied.json()["data"]
    assert data["supplier_invoice_number"] == "SUP-42"
    assert data["notes"] == "From OCR"

    approved = await ac.post(
        f"/api/v1/purchasing/invoices/{invoice_id}/approve",
        headers=headers,
    )
    assert approved.status_code == 200, approved.text

    locked = await ac.post(
        f"/api/v1/purchasing/invoices/{invoice_id}/ocr-apply",
        headers=headers,
        json={"confirm": True, "notes": "nope"},
    )
    assert locked.status_code == 409


@pytest.mark.asyncio
async def test_ocr_apply_tenant_isolation(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    tenant = seed["t1"]
    tenant.expense_approval_threshold = 10
    await db_session.commit()

    created = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "category": "Supplies",
            "amount": 40,
            "description": "iso",
            "payment_method": "cash",
        },
    )
    expense_id = created.json()["data"]["id"]

    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    cross = await ac.post(
        f"/api/v1/expenses/{expense_id}/ocr-apply",
        headers=beta,
        json={"confirm": True, "description": "hack"},
    )
    assert cross.status_code in (403, 404)
