"""Draft purchase return Cancel reason honesty (BR-6.6)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_pr_return_cancel_reason_ui_wired():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "prCancelReason" in page
    assert "Required before Cancel" in page
    assert "Enter a cancel reason before cancelling a purchase return" in page
    assert "cancelReturn" in page
    assert "/purchasing/returns/${ret.id}/cancel" in page or "/purchasing/returns/${" in page
    assert 'aria-label="Purchase return cancel reason"' in page
    assert "aria-label={`Cancel purchase return ${r.id}`}" in page


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _seed_io(db_session, seed, email: str):
    user = m.User(
        tenant_id=seed["t1"].id,
        email=email,
        full_name="IO PR Cancel",
        password_hash=hash_password("SecurePass123!"),
        role="inventory_officer",
        email_verified=True,
        permissions=permissions_for_role("inventory_officer"),
        totp_enabled=False,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _posted_grn(ac, db_session, *, admin, io, seed, vendor: str):
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
            "items": [{"product_id": seed["p1"].id, "quantity": 4, "unit_price": 5, "tax_rate": 0}],
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
                    "received_qty": 4,
                    "accepted_qty": 4,
                    "rejected_qty": 0,
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    body = grn.json()["data"]
    return body["id"], body["items"][0]["id"]


@pytest.mark.asyncio
async def test_purchase_return_cancel_requires_reason_and_persists(client, db_session):
    ac, seed = client
    await _seed_io(db_session, seed, email="io-pr-cancel@alpha.example.com")
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-pr-cancel@alpha.example.com", tenant_slug="alpha")
    grn_id, grn_item_id = await _posted_grn(
        ac, db_session, admin=admin, io=io, seed=seed, vendor="PR Cancel Vendor"
    )

    created = await ac.post(
        "/api/v1/purchasing/returns",
        headers=io,
        json={
            "goods_receipt_id": grn_id,
            "reason": "damaged",
            "notes": "original pr note",
            "items": [{"goods_receipt_item_id": grn_item_id, "quantity": 1}],
        },
    )
    assert created.status_code == 200, created.text
    rid = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "draft"
    assert created.json()["data"]["can_cancel"] is True

    missing = await ac.post(
        f"/api/v1/purchasing/returns/{rid}/cancel",
        headers=io,
        json={},
    )
    assert missing.status_code == 422

    empty = await ac.post(
        f"/api/v1/purchasing/returns/{rid}/cancel",
        headers=io,
        json={"reason": ""},
    )
    assert empty.status_code == 422

    blank = await ac.post(
        f"/api/v1/purchasing/returns/{rid}/cancel",
        headers=io,
        json={"reason": "   "},
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.post(
        f"/api/v1/purchasing/returns/{rid}/cancel",
        headers=io,
        json={"reason": "!!!!"},
    )
    assert garbage.status_code == 422, garbage.text

    ok = await ac.post(
        f"/api/v1/purchasing/returns/{rid}/cancel",
        headers=io,
        json={"reason": "Supplier credit not needed — API hello-world"},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["status"] == "cancelled"
    assert body["can_cancel"] is False
    notes = body.get("notes") or ""
    assert "original pr note" in notes
    assert "Cancel: Supplier credit not needed — API hello-world" in notes

    audit = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.action == "purchase_return_cancelled",
                m.AuditLog.entity_id == rid,
            )
        )
    ).scalar_one()
    assert audit.details.get("reason") == "Supplier credit not needed — API hello-world"


@pytest.mark.asyncio
async def test_purchase_return_cancel_blocked_when_not_draft(client, db_session):
    ac, seed = client
    await _seed_io(db_session, seed, email="io-pr-cancel-post@alpha.example.com")
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-pr-cancel-post@alpha.example.com", tenant_slug="alpha")
    grn_id, grn_item_id = await _posted_grn(
        ac, db_session, admin=admin, io=io, seed=seed, vendor="PR Cancel Posted"
    )

    created = await ac.post(
        "/api/v1/purchasing/returns",
        headers=io,
        json={
            "goods_receipt_id": grn_id,
            "reason": "quality",
            "items": [{"goods_receipt_item_id": grn_item_id, "quantity": 1}],
        },
    )
    assert created.status_code == 200, created.text
    rid = created.json()["data"]["id"]

    posted = await ac.post(f"/api/v1/purchasing/returns/{rid}/post", headers=io)
    assert posted.status_code == 200, posted.text

    blocked = await ac.post(
        f"/api/v1/purchasing/returns/{rid}/cancel",
        headers=io,
        json={"reason": "should fail after post"},
    )
    assert blocked.status_code == 409
    assert "draft" in blocked.json()["detail"].lower()
