"""PO amend reason honesty (BR-6.3)."""

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


def test_po_amend_reason_ui_wired():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "amendReason" in page
    assert "Required amendment reason" in page
    assert 'aria-label="Purchase order amend reason"' in page
    assert 'aria-label="Save purchase order amendment"' in page
    assert "aria-label={`Amend purchase order ${o.id}`}" in page
    assert "Enter an amendment reason before saving" in page
    assert "reason: amendReason.trim() || null" not in page
    assert "reason," in page or "reason\n" in page


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _seed_io(db_session, seed, email: str):
    user = m.User(
        tenant_id=seed["t1"].id,
        email=email,
        full_name="IO PO Amend Reason",
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
async def test_po_amend_requires_reason(client, db_session):
    ac, seed = client
    await _seed_io(db_session, seed, email="io-po-amend-reason@alpha.example.com")
    admin = await _super(ac, seed)
    io = await auth_headers(
        ac, email="io-po-amend-reason@alpha.example.com", tenant_slug="alpha"
    )

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "Amend Reason Vendor", "kind": "supplier"},
    )
    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=io,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "notes": "Original",
            "items": [{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 5}],
        },
    )
    assert created.status_code == 200, created.text
    po_id = created.json()["data"]["id"]
    line = created.json()["data"]["items"][0]

    missing = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/amend",
        headers=io,
        json={
            "notes": "No reason",
            "items": [
                {
                    "product_id": line["product_id"],
                    "quantity": 3,
                    "unit_price": 5,
                }
            ],
        },
    )
    assert missing.status_code == 422

    empty = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/amend",
        headers=io,
        json={
            "reason": "",
            "notes": "Empty reason",
            "items": [
                {
                    "product_id": line["product_id"],
                    "quantity": 3,
                    "unit_price": 5,
                }
            ],
        },
    )
    assert empty.status_code == 422

    blank = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/amend",
        headers=io,
        json={
            "reason": "   ",
            "notes": "Blank reason",
            "items": [
                {
                    "product_id": line["product_id"],
                    "quantity": 3,
                    "unit_price": 5,
                }
            ],
        },
    )
    assert blank.status_code == 422

    ok = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/amend",
        headers=io,
        json={
            "reason": "Qty correction — API hello-world",
            "notes": "Amended",
            "items": [
                {
                    "product_id": line["product_id"],
                    "quantity": 4,
                    "unit_price": 5,
                }
            ],
        },
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["amendment"]["reason"] == "Qty correction — API hello-world"
    assert body["revision_no"] == 1

    audit = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.action == "po_amended",
                m.AuditLog.entity_id == po_id,
            )
        )
    ).scalar_one()
    assert audit.details.get("reason") == "Qty correction — API hello-world"
