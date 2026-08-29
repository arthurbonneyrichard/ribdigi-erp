"""PurchaseOrderCancel.reason OpenAPI honesty (BR-6.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import PurchaseOrderCancel
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_purchase_order_cancel_reason_schema():
    ok = PurchaseOrderCancel.model_validate({"reason": "  Duplicate PO  "})
    assert ok.reason == "Duplicate PO"
    for bad in ("", " ", "!!!", "!!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            PurchaseOrderCancel.model_validate({"reason": bad})
    with pytest.raises(ValidationError):
        PurchaseOrderCancel.model_validate({})


def test_purchase_order_cancel_reason_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Purchase order cancel reason"' in page
    assert "poCancelReason" in page
    assert "aria-label={`Cancel purchase order ${o.id}`}" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "PurchaseOrderCancelReasonValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PurchaseOrderCancelReasonValue" in docs


@pytest.mark.asyncio
async def test_purchase_order_cancel_reason_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]
    tag = f"TIP199 cancel {suffix}"

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": f"TIP199 Vendor {suffix}", "kind": "supplier"},
    )
    assert supplier.status_code == 200, supplier.text
    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "notes": f"tip199 {suffix}",
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 11}],
        },
    )
    assert created.status_code == 200, created.text
    po_id = created.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "   "):
        resp = await ac.post(
            f"/api/v1/purchasing/orders/{po_id}/cancel",
            headers=headers,
            json={"reason": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/cancel",
        headers=headers,
        json={"reason": tag},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["status"] == "cancelled"
    assert f"Cancel: {tag}" in (body.get("notes") or "")
