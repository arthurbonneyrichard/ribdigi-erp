"""SalesOrderCancel.reason OpenAPI honesty (BR-7.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import SalesOrderCancel
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_sales_order_cancel_reason_schema():
    ok = SalesOrderCancel.model_validate({"reason": "  Duplicate order  "})
    assert ok.reason == "Duplicate order"
    for bad in ("", " ", "!!!", "!!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            SalesOrderCancel.model_validate({"reason": bad})
    with pytest.raises(ValidationError):
        SalesOrderCancel.model_validate({})


def test_sales_order_cancel_reason_ui_and_docs():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Sales order cancel reason"' in page
    assert "soCancelReason" in page
    assert "aria-label={`Cancel sales order ${o.id}`}" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "SalesOrderCancelReasonValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "SalesOrderCancelReasonValue" in docs


@pytest.mark.asyncio
async def test_sales_order_cancel_reason_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]
    tag = f"TIP196 cancel {suffix}"

    created = await ac.post(
        "/api/v1/sales/orders",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "notes": f"tip196 {suffix}",
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 9}],
        },
    )
    assert created.status_code == 200, created.text
    oid = created.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "   "):
        resp = await ac.post(
            f"/api/v1/sales/orders/{oid}/cancel",
            headers=headers,
            json={"reason": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        f"/api/v1/sales/orders/{oid}/cancel",
        headers=headers,
        json={"reason": tag},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["status"] == "cancelled"
    assert f"Cancel: {tag}" in (body.get("notes") or "")
