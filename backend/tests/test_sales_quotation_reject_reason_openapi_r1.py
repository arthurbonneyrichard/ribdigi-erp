"""SalesQuotationReject.reason OpenAPI honesty (BR-7.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import SalesQuotationReject
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_sales_quotation_reject_reason_schema():
    ok = SalesQuotationReject.model_validate({"reason": "  Price too high  "})
    assert ok.reason == "Price too high"
    for bad in ("", " ", "!!!", "!!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            SalesQuotationReject.model_validate({"reason": bad})
    with pytest.raises(ValidationError):
        SalesQuotationReject.model_validate({})


def test_sales_quotation_reject_reason_ui_and_docs():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Quotation reject reason"' in page
    assert "quoteRejectReason" in page
    assert 'aria-label={`Reject quotation ${q.id}`}' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "SalesQuotationRejectReasonValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "SalesQuotationRejectReasonValue" in docs


@pytest.mark.asyncio
async def test_sales_quotation_reject_reason_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]
    tag = f"TIP193 reject {suffix}"

    created = await ac.post(
        "/api/v1/sales/quotations",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "valid_days": 14,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 12}],
        },
    )
    assert created.status_code == 200, created.text
    qid = created.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "   "):
        resp = await ac.post(
            f"/api/v1/sales/quotations/{qid}/reject",
            headers=headers,
            json={"reason": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        f"/api/v1/sales/quotations/{qid}/reject",
        headers=headers,
        json={"reason": tag},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["status"] == "rejected"
    assert body["rejection_reason"] == tag
