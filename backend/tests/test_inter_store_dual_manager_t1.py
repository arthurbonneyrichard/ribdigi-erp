"""Stage 4 T1: inter-store dual-manager ship/receive approval (BR-13.2)."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app.inventory import apply_stock_change
from app.rbac import permissions_for_role
from app.security import hash_password
from app.stores import create_store
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_inter_store_ship_receive_requires_store_managers(client, db_session):
    ac, seed = client
    tenant_id = seed["t1"].id
    mgr_from = seed["mgr1"]

    mgr_to = m.User(
        tenant_id=tenant_id,
        email="mgr-dest@alpha.example.com",
        full_name="Dest Manager",
        password_hash=hash_password("SecurePass123!"),
        role="store_manager",
        email_verified=True,
        permissions=permissions_for_role("store_manager"),
        totp_enabled=False,
    )
    db_session.add(mgr_to)
    await db_session.flush()

    from_store = await create_store(
        db_session,
        tenant_id=tenant_id,
        code="SRC1",
        name="Source Store",
        manager_id=mgr_from.id,
    )
    to_store = await create_store(
        db_session,
        tenant_id=tenant_id,
        code="DST1",
        name="Dest Store",
        manager_id=mgr_to.id,
    )
    await db_session.flush()

    from_wh = (
        await db_session.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == tenant_id,
                m.Warehouse.store_id == from_store.id,
            )
        )
    ).scalar_one()
    await apply_stock_change(
        db_session,
        tenant_id=tenant_id,
        product_id=seed["p1"].id,
        quantity_delta=30,
        movement_type="stock_in",
        user_id=mgr_from.id,
        warehouse_id=from_wh.id,
    )
    await db_session.commit()

    mgr_from_h = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    mgr_to_h = await auth_headers(ac, email="mgr-dest@alpha.example.com", tenant_slug="alpha")

    created = await ac.post(
        "/api/v1/stores/transfers",
        headers=mgr_from_h,
        json={
            "from_store_id": from_store.id,
            "to_store_id": to_store.id,
            "submit": True,
            "items": [{"product_id": seed["p1"].id, "quantity": 5}],
        },
    )
    assert created.status_code == 200, created.text
    transfer_id = created.json()["data"]["id"]
    body = created.json()["data"]
    assert body["from_store_manager_id"] == mgr_from.id
    assert body["to_store_manager_id"] == mgr_to.id

    # Destination manager cannot ship
    denied_ship = await ac.post(
        f"/api/v1/stores/transfers/{transfer_id}/ship",
        headers=mgr_to_h,
    )
    assert denied_ship.status_code == 403, denied_ship.text
    assert denied_ship.json()["detail"]["code"] == "TRANSFER_SHIP_FORBIDDEN"

    shipped = await ac.post(
        f"/api/v1/stores/transfers/{transfer_id}/ship",
        headers=mgr_from_h,
    )
    assert shipped.status_code == 200, shipped.text
    assert shipped.json()["data"]["status"] == "in_transit"

    # Source manager cannot receive
    denied_recv = await ac.post(
        f"/api/v1/stores/transfers/{transfer_id}/receive",
        headers=mgr_from_h,
    )
    assert denied_recv.status_code == 403, denied_recv.text
    assert denied_recv.json()["detail"]["code"] == "TRANSFER_RECEIVE_FORBIDDEN"

    received = await ac.post(
        f"/api/v1/stores/transfers/{transfer_id}/receive",
        headers=mgr_to_h,
    )
    assert received.status_code == 200, received.text
    assert received.json()["data"]["status"] == "received"


@pytest.mark.asyncio
async def test_admin_override_ships_with_audit(client, db_session):
    ac, seed = client
    tenant_id = seed["t1"].id
    mgr_from = seed["mgr1"]

    mgr_to = m.User(
        tenant_id=tenant_id,
        email="mgr-dest2@alpha.example.com",
        full_name="Dest Manager 2",
        password_hash=hash_password("SecurePass123!"),
        role="store_manager",
        email_verified=True,
        permissions=permissions_for_role("store_manager"),
        totp_enabled=False,
    )
    db_session.add(mgr_to)
    await db_session.flush()

    from_store = await create_store(
        db_session,
        tenant_id=tenant_id,
        code="SRC2",
        name="Source Store 2",
        manager_id=mgr_from.id,
    )
    to_store = await create_store(
        db_session,
        tenant_id=tenant_id,
        code="DST2",
        name="Dest Store 2",
        manager_id=mgr_to.id,
    )
    await db_session.flush()
    from_wh = (
        await db_session.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == tenant_id,
                m.Warehouse.store_id == from_store.id,
            )
        )
    ).scalar_one()
    await apply_stock_change(
        db_session,
        tenant_id=tenant_id,
        product_id=seed["p1"].id,
        quantity_delta=20,
        movement_type="stock_in",
        user_id=mgr_from.id,
        warehouse_id=from_wh.id,
    )
    await db_session.commit()

    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin_h = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    created = await ac.post(
        "/api/v1/stores/transfers",
        headers=admin_h,
        json={
            "from_store_id": from_store.id,
            "to_store_id": to_store.id,
            "submit": True,
            "items": [{"product_id": seed["p1"].id, "quantity": 3}],
        },
    )
    assert created.status_code == 200, created.text
    transfer_id = created.json()["data"]["id"]

    shipped = await ac.post(
        f"/api/v1/stores/transfers/{transfer_id}/ship",
        headers=admin_h,
    )
    assert shipped.status_code == 200, shipped.text

    db_session.expire_all()
    audits = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == tenant_id,
                m.AuditLog.action == "transfer_manager_override",
                m.AuditLog.entity_id == transfer_id,
            )
        )
    ).scalars().all()
    assert len(audits) >= 1
    assert any((a.details or {}).get("transfer_action") == "ship" for a in audits)
