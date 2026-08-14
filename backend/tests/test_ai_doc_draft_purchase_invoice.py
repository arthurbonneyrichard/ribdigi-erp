"""AI Document Assistant — Create draft purchase invoice from matched PO (BR-21.8)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_ai_doc_draft_purchase_invoice_ui_wired():
    ai = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert "createDraftPurchaseInvoiceFromDoc" in ai
    assert "Create draft purchase invoice" in ai
    assert "/ai/documents/create-purchase-invoice" in ai
    assert "hasPoMatch" in ai


@pytest.mark.asyncio
async def test_create_purchase_invoice_from_po_and_rejects_cancelled(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={
            "name": "AI Doc PI Vendor",
            "kind": "supplier",
            "email": "ai-doc-pi@example.com",
        },
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=admin,
        json={
            "supplier_id": supplier_id,
            "notes": "AI draft PI source",
            "items": [
                {"product_id": seed["p1"].id, "quantity": 3, "unit_price": 10},
            ],
        },
    )
    assert po.status_code == 200, po.text
    po_body = po.json()["data"]
    po_id = po_body["id"]

    missing = await ac.post(
        "/api/v1/ai/documents/create-purchase-invoice",
        headers=admin,
        json={},
    )
    assert missing.status_code == 422, missing.text

    created = await ac.post(
        "/api/v1/ai/documents/create-purchase-invoice",
        headers=admin,
        json={
            "purchase_order_id": po_id,
            "supplier_id": supplier_id,
            "supplier_invoice_number": "SUP-INV-OCR-77",
            "notes": "From OCR review",
            "invoice_date": "2026-08-10",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    inv = body["purchase_invoice"]
    assert inv["status"] == "draft"
    assert inv["purchase_order_id"] == po_id
    assert inv["supplier_id"] == supplier_id
    assert inv["supplier_invoice_number"] == "SUP-INV-OCR-77"
    assert float(inv["total_amount"]) > 0
    assert len(inv["items"]) == 1
    assert float(inv["items"][0]["quantity"]) == 3
    assert body["method"] == "rule_based_ocr_apply_po"
    assert body["po_number"] == po_body["po_number"]

    # Wrong supplier must fail
    other = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={
            "name": "Wrong AI PI Vendor",
            "kind": "supplier",
            "email": "wrong-ai-pi@example.com",
        },
    )
    assert other.status_code == 200, other.text
    bad_supplier = await ac.post(
        "/api/v1/ai/documents/create-purchase-invoice",
        headers=admin,
        json={
            "purchase_order_id": po_id,
            "supplier_id": other.json()["data"]["id"],
        },
    )
    assert bad_supplier.status_code == 400, bad_supplier.text
    assert "supplier" in bad_supplier.json()["detail"].lower()

    # Cancelled PO blocked (separate PO so the draft PI above does not interfere)
    po2 = await ac.post(
        "/api/v1/purchasing/orders",
        headers=admin,
        json={
            "supplier_id": supplier_id,
            "notes": "AI draft PI cancel source",
            "items": [
                {"product_id": seed["p1"].id, "quantity": 1, "unit_price": 4},
            ],
        },
    )
    assert po2.status_code == 200, po2.text
    po2_id = po2.json()["data"]["id"]
    cancelled = await ac.post(
        f"/api/v1/purchasing/orders/{po2_id}/cancel", headers=admin
    )
    assert cancelled.status_code == 200, cancelled.text
    blocked = await ac.post(
        "/api/v1/ai/documents/create-purchase-invoice",
        headers=admin,
        json={"purchase_order_id": po2_id},
    )
    assert blocked.status_code == 400, blocked.text
    assert "cancelled" in blocked.json()["detail"].lower()
