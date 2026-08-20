"""PurchaseReturnCreate.notes OpenAPI honesty (BR-6.6)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app import models as m
from app.rbac import permissions_for_role
from app.schemas import PurchaseReturnCreate
from app.security import hash_password
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]

_BASE = {
    "goods_receipt_id": "grn-1",
    "reason": "damaged",
    "items": [{"goods_receipt_item_id": "gi-1", "quantity": 1}],
}


def test_purchase_return_notes_schema():
    omit = PurchaseReturnCreate.model_validate(_BASE)
    assert omit.notes is None
    nullish = PurchaseReturnCreate.model_validate({**_BASE, "notes": None})
    assert nullish.notes is None
    ok = PurchaseReturnCreate.model_validate({**_BASE, "notes": "  Box crushed  "})
    assert ok.notes == "Box crushed"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            PurchaseReturnCreate.model_validate({**_BASE, "notes": bad})


def test_purchase_return_notes_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Purchase return notes"' in page
    assert "returnNotes.trim() || null" in page
    assert 'aria-label="Create purchase return"' in page
    assert 'aria-label="Purchase return status filter"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Purchase return notes OpenAPI" in agents
    assert "PurchaseReturnNotesValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PurchaseReturnNotesValue" in docs
    assert "Purchase return notes" in docs


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _seed_io(db_session, seed, email: str):
    user = m.User(
        tenant_id=seed["t1"].id,
        email=email,
        full_name="IO Return Notes",
        password_hash=hash_password("SecurePass123!"),
        role="inventory_officer",
        email_verified=True,
        permissions=permissions_for_role("inventory_officer"),
        totp_enabled=False,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _posted_grn(ac, db_session, *, admin, io, seed, vendor: str, qty: float = 6):
    product = await db_session.get(m.Product, seed["p1"].id)
    product.tracks_batches = False
    await db_session.commit()

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={
            "name": vendor,
            "kind": "supplier",
            "email": f"{vendor.replace(' ', '').lower()}@example.com",
        },
    )
    assert supplier.status_code == 200, supplier.text
    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=io,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": qty,
                    "unit_price": 5,
                    "tax_rate": 0,
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    po = created.json()["data"]
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
                    "received_qty": qty,
                    "accepted_qty": qty,
                    "rejected_qty": 0,
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    body = grn.json()["data"]
    return body["id"], body["items"][0]["id"]


@pytest.mark.asyncio
async def test_purchase_return_notes_api_blank_invalid_422(client, db_session):
    ac, seed = client
    await _seed_io(db_session, seed, email="io-ret-notes@alpha.example.com")
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-ret-notes@alpha.example.com", tenant_slug="alpha")
    grn_id, grn_item_id = await _posted_grn(
        ac, db_session, admin=admin, io=io, seed=seed, vendor="Return Notes Vendor"
    )
    suffix = uuid4().hex[:8]
    tag = f"Tip175 notes {suffix}"

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/purchasing/returns",
            headers=io,
            json={
                "goods_receipt_id": grn_id,
                "reason": "damaged",
                "notes": bad,
                "items": [{"goods_receipt_item_id": grn_item_id, "quantity": 1}],
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/purchasing/returns",
        headers=io,
        json={
            "goods_receipt_id": grn_id,
            "reason": "wrong_item",
            "items": [{"goods_receipt_item_id": grn_item_id, "quantity": 1}],
        },
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"].get("notes") in (None, "")

    ok = await ac.post(
        "/api/v1/purchasing/returns",
        headers=io,
        json={
            "goods_receipt_id": grn_id,
            "reason": "quality",
            "notes": f"  {tag}  ",
            "items": [{"goods_receipt_item_id": grn_item_id, "quantity": 1}],
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"].get("notes") == tag, ok.json()
