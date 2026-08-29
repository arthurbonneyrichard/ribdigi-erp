"""PurchaseReturnCancel.reason OpenAPI honesty (BR-6.6)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app import models as m
from app.rbac import permissions_for_role
from app.schemas import PurchaseReturnCancel
from app.security import hash_password
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_purchase_return_cancel_reason_schema():
    ok = PurchaseReturnCancel.model_validate({"reason": "  Supplier credit not needed  "})
    assert ok.reason == "Supplier credit not needed"
    for bad in ("", " ", "!!!", "!!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            PurchaseReturnCancel.model_validate({"reason": bad})
    with pytest.raises(ValidationError):
        PurchaseReturnCancel.model_validate({})


def test_purchase_return_cancel_reason_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Purchase return cancel reason"' in page
    assert "prCancelReason" in page
    assert "aria-label={`Cancel purchase return ${r.id}`}" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "PurchaseReturnCancelReasonValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PurchaseReturnCancelReasonValue" in docs


async def _super(ac, seed):
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _seed_io(db_session, seed, email: str):
    user = m.User(
        tenant_id=seed["t1"].id,
        email=email,
        full_name="IO PR Cancel OpenAPI",
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
async def test_purchase_return_cancel_reason_api_blank_invalid_422(client, db_session):
    ac, seed = client
    suffix = uuid4().hex[:8]
    tag = f"TIP201 cancel {suffix}"
    await _seed_io(db_session, seed, email=f"io-tip201-{suffix}@alpha.example.com")
    admin = await _super(ac, seed)
    io = await auth_headers(
        ac, email=f"io-tip201-{suffix}@alpha.example.com", tenant_slug="alpha"
    )

    product = await db_session.get(m.Product, seed["p1"].id)
    product.tracks_batches = False
    await db_session.commit()

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": f"TIP201 Vendor {suffix}", "kind": "supplier"},
    )
    assert supplier.status_code == 200, supplier.text
    created_po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=io,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "items": [{"product_id": seed["p1"].id, "quantity": 3, "unit_price": 5, "tax_rate": 0}],
        },
    )
    assert created_po.status_code == 200, created_po.text
    po = created_po.json()["data"]
    po_row = await db_session.get(m.PurchaseOrder, po["id"])
    po_row.status = "sent"
    await db_session.commit()

    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=io,
        json={
            "purchase_order_id": po["id"],
            "items": [
                {
                    "po_item_id": po["items"][0]["id"],
                    "received_qty": 3,
                    "accepted_qty": 3,
                    "rejected_qty": 0,
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    grn_body = grn.json()["data"]

    created = await ac.post(
        "/api/v1/purchasing/returns",
        headers=io,
        json={
            "goods_receipt_id": grn_body["id"],
            "reason": "damaged",
            "notes": f"tip201 {suffix}",
            "items": [{"goods_receipt_item_id": grn_body["items"][0]["id"], "quantity": 1}],
        },
    )
    assert created.status_code == 200, created.text
    rid = created.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "   "):
        resp = await ac.post(
            f"/api/v1/purchasing/returns/{rid}/cancel",
            headers=io,
            json={"reason": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        f"/api/v1/purchasing/returns/{rid}/cancel",
        headers=io,
        json={"reason": tag},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["status"] == "cancelled"
    assert f"Cancel: {tag}" in (body.get("notes") or "")
