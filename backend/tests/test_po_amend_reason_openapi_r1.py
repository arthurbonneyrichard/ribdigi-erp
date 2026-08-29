"""PurchaseOrderAmend.reason OpenAPI honesty (BR-6.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app import models as m
from app.rbac import permissions_for_role
from app.schemas import PurchaseOrderAmend
from app.security import hash_password
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_purchase_order_amend_reason_schema():
    ok = PurchaseOrderAmend.model_validate({"reason": "  Qty correction mid-PO  "})
    assert ok.reason == "Qty correction mid-PO"
    for bad in ("", " ", "!!!", "!!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            PurchaseOrderAmend.model_validate({"reason": bad})
    with pytest.raises(ValidationError):
        PurchaseOrderAmend.model_validate({})


def test_purchase_order_amend_reason_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Purchase order amend reason"' in page
    assert 'aria-label="Save purchase order amendment"' in page
    assert "aria-label={`Amend purchase order ${o.id}`}" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "PurchaseOrderAmendReasonValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PurchaseOrderAmendReasonValue" in docs
    brd = (ROOT / "docs/BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    assert "PurchaseOrderAmendReasonValue" in brd


async def _seed_io(db_session, seed, email: str):
    user = m.User(
        tenant_id=seed["t1"].id,
        email=email,
        full_name="IO PO Amend OpenAPI",
        password_hash=hash_password("SecurePass123!"),
        role="inventory_officer",
        email_verified=True,
        permissions=permissions_for_role("inventory_officer"),
        totp_enabled=False,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_purchase_order_amend_reason_api_blank_invalid_422(client, db_session):
    ac, seed = client
    suffix = uuid4().hex[:8]
    tag = f"Tip206 amend {suffix}"
    await _seed_io(db_session, seed, email=f"io-tip206-{suffix}@alpha.example.com")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    io = await auth_headers(
        ac, email=f"io-tip206-{suffix}@alpha.example.com", tenant_slug="alpha"
    )

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": f"TIP206 Vendor {suffix}", "kind": "supplier"},
    )
    assert supplier.status_code == 200, supplier.text
    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=io,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "notes": "tip206 original",
            "items": [{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 5}],
        },
    )
    assert created.status_code == 200, created.text
    po_id = created.json()["data"]["id"]
    line = created.json()["data"]["items"][0]
    items = [
        {
            "product_id": line["product_id"],
            "quantity": 3,
            "unit_price": 5,
        }
    ]

    for bad in ("", "!!!", "http://evil", "   "):
        resp = await ac.post(
            f"/api/v1/purchasing/orders/{po_id}/amend",
            headers=io,
            json={"reason": bad, "notes": "bad", "items": items},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/amend",
        headers=io,
        json={"reason": tag, "notes": "Amended tip206", "items": items},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["amendment"]["reason"] == tag
    assert body["revision_no"] == 1
