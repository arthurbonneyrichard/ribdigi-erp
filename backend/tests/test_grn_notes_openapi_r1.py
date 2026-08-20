"""GrnCreate.notes OpenAPI honesty (BR-6.4)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app import models as m
from app.rbac import permissions_for_role
from app.schemas import GrnCreate
from app.security import hash_password
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]

_BASE = {
    "purchase_order_id": "po-1",
    "items": [
        {
            "po_item_id": "poi-1",
            "received_qty": 1,
            "accepted_qty": 1,
            "rejected_qty": 0,
        }
    ],
}


def test_grn_notes_schema():
    omit = GrnCreate.model_validate(_BASE)
    assert omit.notes is None
    ok = GrnCreate.model_validate({**_BASE, "notes": "  Delivery OK  "})
    assert ok.notes == "Delivery OK"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            GrnCreate.model_validate({**_BASE, "notes": bad})


def test_grn_notes_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="GRN notes"' in page
    assert "grnNotes.trim() || null" in page
    assert 'aria-label="Post GRN"' in page
    assert 'aria-label="Receive all accepted"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "GRN notes OpenAPI" in agents
    assert "GrnNotesValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "GrnNotesValue" in docs
    assert "GRN notes" in docs


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _seed_io(db_session, seed, email: str):
    user = m.User(
        tenant_id=seed["t1"].id,
        email=email,
        full_name="IO GRN Notes",
        password_hash=hash_password("SecurePass123!"),
        role="inventory_officer",
        email_verified=True,
        permissions=permissions_for_role("inventory_officer"),
        totp_enabled=False,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _sent_po(ac, db_session, *, admin, io, seed, vendor: str, qty: float = 4):
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
    return po


@pytest.mark.asyncio
async def test_grn_notes_api_blank_invalid_422(client, db_session):
    ac, seed = client
    await _seed_io(db_session, seed, email="io-grn-notes@alpha.example.com")
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-grn-notes@alpha.example.com", tenant_slug="alpha")
    po = await _sent_po(
        ac, db_session, admin=admin, io=io, seed=seed, vendor="GRN Notes Vendor"
    )
    suffix = uuid4().hex[:8]
    tag = f"Tip177 notes {suffix}"
    item = {
        "po_item_id": po["items"][0]["id"],
        "received_qty": 1,
        "accepted_qty": 1,
        "rejected_qty": 0,
    }

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/purchasing/grn",
            headers=io,
            json={"purchase_order_id": po["id"], "notes": bad, "items": [item]},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/purchasing/grn",
        headers=io,
        json={"purchase_order_id": po["id"], "items": [item]},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"].get("notes") in (None, "")

    ok = await ac.post(
        "/api/v1/purchasing/grn",
        headers=io,
        json={
            "purchase_order_id": po["id"],
            "notes": f"  {tag}  ",
            "items": [
                {
                    "po_item_id": po["items"][0]["id"],
                    "received_qty": 1,
                    "accepted_qty": 1,
                    "rejected_qty": 0,
                }
            ],
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"].get("notes") == tag, ok.json()
