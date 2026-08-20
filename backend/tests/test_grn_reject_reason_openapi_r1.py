"""GrnItemCreate.rejection_reason OpenAPI honesty (BR-6.4)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app import models as m
from app.rbac import permissions_for_role
from app.schemas import GrnItemCreate
from app.security import hash_password
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_grn_rejection_reason_schema():
    ok = GrnItemCreate.model_validate(
        {
            "po_item_id": "x",
            "received_qty": 10,
            "accepted_qty": 8,
            "rejected_qty": 2,
            "rejection_reason": "  Damaged packaging  ",
        }
    )
    assert ok.rejection_reason == "Damaged packaging"

    # Full accept — reason optional
    GrnItemCreate.model_validate(
        {"po_item_id": "x", "received_qty": 5, "accepted_qty": 5, "rejected_qty": 0}
    )

    with pytest.raises(ValidationError) as explicit:
        GrnItemCreate.model_validate(
            {
                "po_item_id": "x",
                "received_qty": 10,
                "accepted_qty": 8,
                "rejected_qty": 2,
            }
        )
    assert "rejection_reason" in str(explicit.value).lower()

    # Inferred reject when accepted < received and rejected_qty omitted/0
    with pytest.raises(ValidationError) as inferred:
        GrnItemCreate.model_validate(
            {
                "po_item_id": "x",
                "received_qty": 10,
                "accepted_qty": 7,
                "rejected_qty": 0,
            }
        )
    assert "rejection_reason" in str(inferred.value).lower()

    for bad in ("", " ", "!!!", "!!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            GrnItemCreate.model_validate(
                {
                    "po_item_id": "x",
                    "received_qty": 10,
                    "accepted_qty": 8,
                    "rejected_qty": 2,
                    "rejection_reason": bad,
                }
            )
        # Garbage still 422 even when no reject qty (optional field honesty)
        with pytest.raises(ValidationError):
            GrnItemCreate.model_validate(
                {
                    "po_item_id": "x",
                    "received_qty": 5,
                    "accepted_qty": 5,
                    "rejected_qty": 0,
                    "rejection_reason": bad,
                }
            )


def test_grn_rejection_reason_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "Enter a rejection reason for lines with rejected qty" in page
    assert "Rejected qty requires a reason" in page
    assert "aria-label={`GRN rejection reason ${i.id}`}" in page
    assert 'aria-label="Post GRN"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "GrnRejectionReasonValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "GrnRejectionReasonValue" in docs
    brd = (ROOT / "docs/BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    assert "GrnRejectionReasonValue" in brd


async def _seed_io(db_session, seed, email: str):
    user = m.User(
        tenant_id=seed["t1"].id,
        email=email,
        full_name="IO GRN Reject OpenAPI",
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
async def test_grn_rejection_reason_api_blank_invalid_422(client, db_session):
    ac, seed = client
    suffix = uuid4().hex[:8]
    tag = f"Tip208 damaged {suffix}"
    await _seed_io(db_session, seed, email=f"io-tip208-{suffix}@alpha.example.com")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    io = await auth_headers(
        ac, email=f"io-tip208-{suffix}@alpha.example.com", tenant_slug="alpha"
    )

    product = await db_session.get(m.Product, seed["p1"].id)
    product.tracks_batches = False
    await db_session.commit()

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": f"TIP208 Vendor {suffix}", "kind": "supplier"},
    )
    assert supplier.status_code == 200, supplier.text
    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=io,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "notes": "tip208",
            "items": [{"product_id": seed["p1"].id, "quantity": 10, "unit_price": 5}],
        },
    )
    assert created.status_code == 200, created.text
    po_id = created.json()["data"]["id"]
    po_item_id = created.json()["data"]["items"][0]["id"]
    sent = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/send?to=tip208@example.com",
        headers=io,
    )
    assert sent.status_code == 200, sent.text

    for bad in ("", "!!!", "http://evil", "   "):
        resp = await ac.post(
            "/api/v1/purchasing/grn",
            headers=io,
            json={
                "purchase_order_id": po_id,
                "items": [
                    {
                        "po_item_id": po_item_id,
                        "received_qty": 10,
                        "accepted_qty": 8,
                        "rejected_qty": 2,
                        "rejection_reason": bad,
                    }
                ],
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        "/api/v1/purchasing/grn",
        headers=io,
        json={
            "purchase_order_id": po_id,
            "items": [
                {
                    "po_item_id": po_item_id,
                    "received_qty": 10,
                    "accepted_qty": 8,
                    "rejected_qty": 2,
                    "rejection_reason": tag,
                }
            ],
        },
    )
    assert ok.status_code == 200, ok.text
    item = ok.json()["data"]["items"][0]
    assert item["rejection_reason"] == tag
    assert float(item["rejected_qty"]) == 2
