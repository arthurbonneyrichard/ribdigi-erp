"""Purchase request workflow: create → submit → approve → convert to PO."""

from __future__ import annotations

import pyotp
import pytest

from app.rbac import permissions_for_role
from app.security import hash_password
from app import models as m
from tests.conftest import auth_headers


async def _super(ac, seeded):
    code = pyotp.TOTP(seeded["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _manager(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _seed_inventory_officer(db_session, seeded):
    user = m.User(
        tenant_id=seeded["t1"].id,
        email="io@alpha.example.com",
        full_name="Alpha Inventory Officer",
        password_hash=hash_password("SecurePass123!"),
        role="inventory_officer",
        email_verified=True,
        permissions=permissions_for_role("inventory_officer"),
        totp_enabled=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_purchase_request_happy_path_convert(client, db_session):
    ac, seeded = client
    await _seed_inventory_officer(db_session, seeded)
    io = await auth_headers(ac, email="io@alpha.example.com", tenant_slug="alpha")
    mgr = await _manager(ac)
    admin = await _super(ac, seeded)

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "PR Supplier Co", "kind": "supplier"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]
    product_id = seeded["p1"].id

    created = await ac.post(
        "/api/v1/purchasing/requests",
        headers=io,
        json={
            "preferred_supplier_id": supplier_id,
            "department": "Front Store",
            "notes": "Restock widgets",
            "items": [{"product_id": product_id, "quantity": 12}],
        },
    )
    assert created.status_code == 200, created.text
    pr = created.json()["data"]
    assert pr["status"] == "draft"
    assert pr["request_number"].startswith("R")
    request_id = pr["id"]

    submitted = await ac.post(
        f"/api/v1/purchasing/requests/{request_id}/submit",
        headers=io,
        json={},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["data"]["status"] == "pending"

    # No self-approve: IO cannot approve own PR even with elevate — use manager
    self_approve = await ac.post(
        f"/api/v1/purchasing/requests/{request_id}/approve",
        headers=io,
        json={},
    )
    assert self_approve.status_code == 403

    approved = await ac.post(
        f"/api/v1/purchasing/requests/{request_id}/approve",
        headers=mgr,
        json={},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["status"] == "approved"

    converted = await ac.post(
        f"/api/v1/purchasing/requests/{request_id}/convert",
        headers=io,
        json={},
    )
    assert converted.status_code == 200, converted.text
    body = converted.json()["data"]
    assert body["status"] == "converted"
    assert body["converted_po_id"]
    assert body["purchase_order"]["status"] == "draft"
    assert body["purchase_order"]["supplier_id"] == supplier_id
    assert len(body["purchase_order"]["items"]) == 1
    assert body["purchase_order"]["items"][0]["quantity"] == 12.0


@pytest.mark.asyncio
async def test_purchase_request_reject(client, db_session):
    ac, seeded = client
    await _seed_inventory_officer(db_session, seeded)
    io = await auth_headers(ac, email="io@alpha.example.com", tenant_slug="alpha")
    mgr = await _manager(ac)

    created = await ac.post(
        "/api/v1/purchasing/requests",
        headers=io,
        json={"items": [{"product_id": seeded["p1"].id, "quantity": 3}]},
    )
    assert created.status_code == 200, created.text
    request_id = created.json()["data"]["id"]
    await ac.post(f"/api/v1/purchasing/requests/{request_id}/submit", headers=io, json={})

    rejected = await ac.post(
        f"/api/v1/purchasing/requests/{request_id}/reject",
        headers=mgr,
        json={"reason": "Not needed"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["data"]["status"] == "rejected"
    assert rejected.json()["data"]["rejection_reason"] == "Not needed"

    convert = await ac.post(
        f"/api/v1/purchasing/requests/{request_id}/convert",
        headers=io,
        json={"supplier_id": seeded["supplier2"].id},
    )
    assert convert.status_code == 409


@pytest.mark.asyncio
async def test_purchase_request_tenant_isolation(client, db_session):
    ac, seeded = client
    await _seed_inventory_officer(db_session, seeded)
    io = await auth_headers(ac, email="io@alpha.example.com", tenant_slug="alpha")
    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")

    created = await ac.post(
        "/api/v1/purchasing/requests",
        headers=io,
        json={"items": [{"product_id": seeded["p1"].id, "quantity": 2}]},
    )
    assert created.status_code == 200, created.text
    request_id = created.json()["data"]["id"]

    listed = await ac.get("/api/v1/purchasing/requests", headers=beta)
    # cashier lacks purchasing:read
    assert listed.status_code in {200, 403}
    if listed.status_code == 200:
        ids = {r["id"] for r in listed.json()["data"]}
        assert request_id not in ids

    foreign = await ac.get(f"/api/v1/purchasing/requests/{request_id}", headers=beta)
    assert foreign.status_code in {403, 404}
