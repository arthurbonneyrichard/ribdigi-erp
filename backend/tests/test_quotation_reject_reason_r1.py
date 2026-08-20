"""Quotation Reject reason honesty (BR-7.2) — FE/API required reason."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_quotation_reject_reason_ui_wired():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "quoteRejectReason" in sales
    assert "Enter a reject reason before rejecting a quotation" in sales
    assert "rejection_reason" in sales
    assert "Required before Reject" in sales
    assert 'aria-label="Quotation reject reason"' in sales
    assert "body = { ...body, reason }" in sales or "reason" in sales
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "SalesQuotationRejectReasonValue" in agents


@pytest.mark.asyncio
async def test_quotation_reject_requires_and_persists_reason(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

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

    missing = await ac.post(f"/api/v1/sales/quotations/{qid}/reject", headers=headers, json={})
    assert missing.status_code == 422, missing.text

    blank = await ac.post(
        f"/api/v1/sales/quotations/{qid}/reject",
        headers=headers,
        json={"reason": "  "},
    )
    # OpenAPI honesty: strip + SalesQuotationRejectReasonValue → 422 (was service 400).
    assert blank.status_code == 422, blank.text

    garbage = await ac.post(
        f"/api/v1/sales/quotations/{qid}/reject",
        headers=headers,
        json={"reason": "!!!!"},
    )
    assert garbage.status_code == 422, garbage.text

    ok = await ac.post(
        f"/api/v1/sales/quotations/{qid}/reject",
        headers=headers,
        json={"reason": "Price too high — API hello-world"},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["status"] == "rejected"
    assert body["rejection_reason"] == "Price too high — API hello-world"
