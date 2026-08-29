"""SalesReturnCancel.reason OpenAPI honesty (BR-7.5)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import SalesReturnCancel
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_sales_return_cancel_reason_schema():
    ok = SalesReturnCancel.model_validate({"reason": "  Customer kept goods  "})
    assert ok.reason == "Customer kept goods"
    for bad in ("", " ", "!!!", "!!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            SalesReturnCancel.model_validate({"reason": bad})
    with pytest.raises(ValidationError):
        SalesReturnCancel.model_validate({})


def test_sales_return_cancel_reason_ui_and_docs():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Sales return cancel reason"' in page
    assert "srCancelReason" in page
    assert "aria-label={`Cancel sales return ${r.id}`}" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "SalesReturnCancelReasonValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "SalesReturnCancelReasonValue" in docs


@pytest.mark.asyncio
async def test_sales_return_cancel_reason_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]
    tag = f"TIP198 cancel {suffix}"

    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "items": [{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 25}],
        },
    )
    assert inv.status_code == 200, inv.text
    iid = inv.json()["data"]["id"]
    posted = await ac.post(f"/api/v1/sales/invoices/{iid}/post", headers=headers)
    assert posted.status_code == 200, posted.text

    created = await ac.post(
        "/api/v1/sales/returns",
        headers=headers,
        json={
            "sales_invoice_id": iid,
            "reason": "damaged",
            "restock": False,
            "notes": f"tip198 {suffix}",
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "condition": "discard"}],
        },
    )
    assert created.status_code == 200, created.text
    rid = created.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "   "):
        resp = await ac.post(
            f"/api/v1/sales/returns/{rid}/cancel",
            headers=headers,
            json={"reason": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        f"/api/v1/sales/returns/{rid}/cancel",
        headers=headers,
        json={"reason": tag},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["status"] == "cancelled"
    assert f"Cancel: {tag}" in (body.get("notes") or "")
