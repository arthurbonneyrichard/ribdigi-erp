"""Inter-store transfer dual-manager approval (BR-13.2)."""

from __future__ import annotations

import pyotp
import pytest

from app.rbac import permissions_for_role
from app.security import hash_password
from app.stores import create_store
from app import models as m
from app.inventory import apply_warehouse_stock_change
from app.stores import warehouse_for_store
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_transfer_dual_approval_then_ship_receive(client, db_session, seeded):
    ac, seed = client
    admin = await _super(ac, seed)
    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    mgr2 = m.User(
        tenant_id=seed["t1"].id,
        email="mgr2@alpha.example.com",
        full_name="Dest Manager",
        password_hash=hash_password("SecurePass123!"),
        role="store_manager",
        email_verified=True,
        permissions=permissions_for_role("store_manager"),
        totp_enabled=False,
    )
    db_session.add(mgr2)
    await db_session.commit()
    await db_session.refresh(mgr2)
    mgr2h = await auth_headers(ac, email="mgr2@alpha.example.com", tenant_slug="alpha")

    from_store = await create_store(
        db_session,
        tenant_id=seed["t1"].id,
        name="Source Store",
        code="SRC",
        manager_id=seed["mgr1"].id,
    )
    to_store = await create_store(
        db_session,
        tenant_id=seed["t1"].id,
        name="Dest Store",
        code="DST",
        manager_id=mgr2.id,
    )
    await db_session.commit()

    # Seed stock at source warehouse
    wh = await warehouse_for_store(db_session, seed["t1"].id, from_store.id)
    await apply_warehouse_stock_change(
        db_session,
        tenant_id=seed["t1"].id,
        warehouse_id=wh.id,
        product_id=seed["p1"].id,
        quantity_delta=20,
    )
    product = await db_session.get(m.Product, seed["p1"].id)
    product.stock_qty = float(product.stock_qty or 0) + 20
    await db_session.commit()

    created = await ac.post(
        "/api/v1/stores/transfers",
        headers=admin,
        json={
            "from_store_id": from_store.id,
            "to_store_id": to_store.id,
            "submit": True,
            "items": [{"product_id": seed["p1"].id, "quantity": 5}],
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    tid = body["id"]
    assert body["status"] == "requested"
    assert body["awaiting_approval"] == "source"
    assert body["can_ship"] is False

    # Cannot ship before approvals
    early = await ac.post(f"/api/v1/stores/transfers/{tid}/ship", headers=admin)
    assert early.status_code == 409

    # Dest manager cannot do source step
    wrong = await ac.post(f"/api/v1/stores/transfers/{tid}/approve", headers=mgr2h)
    assert wrong.status_code == 403

    src = await ac.post(f"/api/v1/stores/transfers/{tid}/approve", headers=mgr)
    assert src.status_code == 200, src.text
    assert src.json()["data"]["awaiting_approval"] == "dest"
    assert src.json()["data"]["can_ship"] is False

    # Same manager cannot do both
    dup = await ac.post(f"/api/v1/stores/transfers/{tid}/approve", headers=mgr)
    assert dup.status_code == 403

    dest = await ac.post(f"/api/v1/stores/transfers/{tid}/approve", headers=mgr2h)
    assert dest.status_code == 200, dest.text
    assert dest.json()["data"]["fully_approved"] is True
    assert dest.json()["data"]["can_ship"] is True

    shipped = await ac.post(f"/api/v1/stores/transfers/{tid}/ship", headers=admin)
    assert shipped.status_code == 200, shipped.text
    assert shipped.json()["data"]["status"] == "in_transit"

    received = await ac.post(f"/api/v1/stores/transfers/{tid}/receive", headers=admin)
    assert received.status_code == 200, received.text
    assert received.json()["data"]["status"] == "received"


@pytest.mark.asyncio
async def test_transfer_reject_cancels(client, db_session, seeded):
    ac, seed = client
    admin = await _super(ac, seed)
    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    from_store = await create_store(
        db_session, tenant_id=seed["t1"].id, name="A", code="TA", manager_id=seed["mgr1"].id
    )
    to_store = await create_store(
        db_session, tenant_id=seed["t1"].id, name="B", code="TB", manager_id=seed["mgr1"].id
    )
    await db_session.commit()

    created = await ac.post(
        "/api/v1/stores/transfers",
        headers=admin,
        json={
            "from_store_id": from_store.id,
            "to_store_id": to_store.id,
            "submit": True,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    tid = created.json()["data"]["id"]
    rejected = await ac.post(
        f"/api/v1/stores/transfers/{tid}/reject",
        headers=mgr,
        json={"reason": "Not needed"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["data"]["status"] == "cancelled"
    assert rejected.json()["data"]["rejection_reason"] == "Not needed"
