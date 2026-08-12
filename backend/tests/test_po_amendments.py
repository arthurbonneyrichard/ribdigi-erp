"""Purchase order amendment tracking (BR-6.3)."""

from __future__ import annotations

import pyotp
import pytest

from app.emailer import clear_dev_outbox, get_dev_outbox
from app.rbac import permissions_for_role
from app.security import hash_password
from app import models as m
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _seed_io(db_session, seed):
    user = m.User(
        tenant_id=seed["t1"].id,
        email="io-po-amend@alpha.example.com",
        full_name="IO PO Amend",
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
async def test_amend_draft_po_lines_and_history(client, db_session):
    ac, seed = client
    await _seed_io(db_session, seed)
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-po-amend@alpha.example.com", tenant_slug="alpha")

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "Amend Vendor", "kind": "supplier", "email": "amend-vendor@example.com"},
    )
    supplier_id = supplier.json()["data"]["id"]
    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=io,
        json={
            "supplier_id": supplier_id,
            "notes": "Original",
            "items": [{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 5}],
        },
    )
    assert created.status_code == 200, created.text
    po_id = created.json()["data"]["id"]
    assert created.json()["data"]["revision_no"] == 0
    assert created.json()["data"]["can_amend"] is True

    amended = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/amend",
        headers=io,
        json={
            "reason": "Qty correction",
            "notes": "Amended notes",
            "items": [{"product_id": seed["p1"].id, "quantity": 5, "unit_price": 4}],
        },
    )
    assert amended.status_code == 200, amended.text
    body = amended.json()["data"]
    assert body["status"] == "draft"
    assert body["revision_no"] == 1
    assert body["notes"] == "Amended notes"
    assert body["items"][0]["quantity"] == 5.0
    assert body["items"][0]["unit_price"] == 4.0
    assert body["amendment"]["revision_no"] == 1
    assert body["amendment"]["reason"] == "Qty correction"
    assert body["amendment"]["notified_supplier"] is False
    assert len(body["amendments"]) == 1
    assert body["amendments"][0]["changes"]["before"]["items"][0]["quantity"] == 2.0
    assert body["amendments"][0]["changes"]["after"]["items"][0]["quantity"] == 5.0

    hist = await ac.get(f"/api/v1/purchasing/orders/{po_id}/amendments", headers=io)
    assert hist.status_code == 200
    assert len(hist.json()["data"]) == 1


@pytest.mark.asyncio
async def test_amend_sent_po_with_notify(client, db_session, monkeypatch):
    ac, seed = client
    await _seed_io(db_session, seed)
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-po-amend@alpha.example.com", tenant_slug="alpha")
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")
    clear_dev_outbox()

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "Notify Vendor", "kind": "supplier", "email": "notify-vendor@example.com"},
    )
    supplier_id = supplier.json()["data"]["id"]
    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=io,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 10}],
        },
    )
    po_id = created.json()["data"]["id"]
    sent = await ac.post(f"/api/v1/purchasing/orders/{po_id}/send", headers=io)
    assert sent.status_code == 200, sent.text
    clear_dev_outbox()

    amended = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/amend",
        headers=io,
        json={
            "items": [{"product_id": seed["p1"].id, "quantity": 3, "unit_price": 10}],
            "reason": "Extra units",
            "notify_supplier": True,
        },
    )
    assert amended.status_code == 200, amended.text
    body = amended.json()["data"]
    assert body["status"] == "sent"
    assert body["revision_no"] == 1
    assert body["delivery"]["amended"] is True
    assert body["amendment"]["notified_supplier"] is True
    out = get_dev_outbox()
    assert out and "amended" in out[0]["subject"].lower()
    assert out[0]["to"] == ["notify-vendor@example.com"]


@pytest.mark.asyncio
async def test_amend_blocked_after_receipt(client, db_session):
    ac, seed = client
    await _seed_io(db_session, seed)
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-po-amend@alpha.example.com", tenant_slug="alpha")

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "Receipt Vendor", "kind": "supplier", "email": "r@example.com"},
    )
    supplier_id = supplier.json()["data"]["id"]
    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=io,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 4, "unit_price": 2}],
        },
    )
    po_id = created.json()["data"]["id"]
    # Force status to sent without email dependency
    po = await db_session.get(m.PurchaseOrder, po_id)
    po.status = "sent"
    await db_session.commit()

    items = created.json()["data"]["items"]
    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=io,
        json={
            "purchase_order_id": po_id,
            "items": [{"po_item_id": items[0]["id"], "received_qty": 1, "accepted_qty": 1}],
        },
    )
    assert grn.status_code == 200, grn.text

    blocked = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/amend",
        headers=io,
        json={"items": [{"product_id": seed["p1"].id, "quantity": 8, "unit_price": 2}]},
    )
    assert blocked.status_code == 409
    assert "received" in blocked.json()["detail"].lower()


@pytest.mark.asyncio
async def test_amend_noop_rejected(client, db_session):
    ac, seed = client
    await _seed_io(db_session, seed)
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email="io-po-amend@alpha.example.com", tenant_slug="alpha")
    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "Noop Vendor", "kind": "supplier"},
    )
    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=io,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "notes": "Same",
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 3}],
        },
    )
    po_id = created.json()["data"]["id"]
    empty = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/amend",
        headers=io,
        json={},
    )
    assert empty.status_code == 400
    same = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/amend",
        headers=io,
        json={
            "notes": "Same",
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 3}],
        },
    )
    assert same.status_code == 400
