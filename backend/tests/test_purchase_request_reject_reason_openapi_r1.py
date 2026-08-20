"""PurchaseRequestReject.reason OpenAPI honesty (BR-6.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import PurchaseRequestReject
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_purchase_request_reject_reason_schema():
    ok = PurchaseRequestReject.model_validate({"reason": "  Budget freeze  "})
    assert ok.reason == "Budget freeze"
    for bad in ("", " ", "!!!", "!!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            PurchaseRequestReject.model_validate({"reason": bad})
    with pytest.raises(ValidationError):
        PurchaseRequestReject.model_validate({})


def test_purchase_request_reject_reason_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Purchase request reject reason"' in page
    assert "prRejectReason" in page
    assert 'aria-label={`Reject purchase request ${r.id}`}' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "PurchaseRequestRejectReasonValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PurchaseRequestRejectReasonValue" in docs


@pytest.mark.asyncio
async def test_purchase_request_reject_reason_api_blank_invalid_422(client):
    import pyotp

    ac, seed = client
    # Create as company admin, reject as super (no self-reject).
    creator = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    approver = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]
    tag = f"TIP192 reject {suffix}"

    created = await ac.post(
        "/api/v1/purchasing/requests",
        headers=creator,
        json={
            "department": "Ops",
            "items": [{"product_id": seed["p1"].id, "quantity": 2}],
        },
    )
    assert created.status_code == 200, created.text
    rid = created.json()["data"]["id"]

    submitted = await ac.post(f"/api/v1/purchasing/requests/{rid}/submit", headers=creator)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["data"]["status"] == "pending"

    for bad in ("", "!!!", "http://evil", "   "):
        resp = await ac.post(
            f"/api/v1/purchasing/requests/{rid}/reject",
            headers=approver,
            json={"reason": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        f"/api/v1/purchasing/requests/{rid}/reject",
        headers=approver,
        json={"reason": tag},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["status"] == "rejected"
    assert body["rejection_reason"] == tag
