"""Customer profile: code, walk-in/registered type, status, contacts, history."""

from __future__ import annotations

import pytest

from tests.conftest import auth_headers


async def _sales(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_customer_profile_contacts_history_and_deactivate(client):
    ac, seed = client
    headers = await _sales(ac)

    created = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={
            "name": "Retail Buyer",
            "code": "CUST-01",
            "party_type": "registered",
            "email": "buyer@example.com",
            "phone": "+233200000010",
            "address": "12 Market St",
            "notes": "Preferred account",
            "payment_terms_days": 14,
            "credit_limit": 2500,
            "contacts": [
                {
                    "name": "Ama Desk",
                    "email": "ama@example.com",
                    "is_primary": True,
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    customer = created.json()["data"]
    assert customer["code"] == "CUST-01"
    assert customer["party_type"] == "registered"
    assert customer["status"] == "active"
    assert customer["payment_terms_days"] == 14
    assert len(customer["contacts"]) == 1

    dup = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Other", "code": "cust-01"},
    )
    assert dup.status_code == 409

    bad_type = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Bad", "party_type": "wholesale"},
    )
    assert bad_type.status_code == 400

    walk_in = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Counter Guest", "party_type": "walk-in", "code": "WI-1"},
    )
    assert walk_in.status_code == 200, walk_in.text
    assert walk_in.json()["data"]["party_type"] == "walk-in"

    patched = await ac.patch(
        f"/api/v1/customers/{customer['id']}",
        headers=headers,
        json={"payment_terms_days": 30, "notes": "Updated"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["payment_terms_days"] == 30

    contact = await ac.post(
        f"/api/v1/customers/{customer['id']}/contacts",
        headers=headers,
        json={"name": "Kojo Ops", "email": "kojo@example.com", "is_primary": True},
    )
    assert contact.status_code == 200, contact.text
    detail = await ac.get(f"/api/v1/customers/{customer['id']}", headers=headers)
    contacts = detail.json()["data"]["contacts"]
    assert len(contacts) == 2
    assert sum(1 for c in contacts if c["is_primary"]) == 1

    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer["id"],
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 5}],
        },
    )
    assert inv.status_code == 200, inv.text

    history = await ac.get(f"/api/v1/customers/{customer['id']}/history", headers=headers)
    assert history.status_code == 200, history.text
    assert len(history.json()["data"]["invoices"]) >= 1

    listed = await ac.get("/api/v1/customers", headers=headers)
    assert listed.status_code == 200
    codes = {row["code"] for row in listed.json()["data"] if row.get("code")}
    assert "CUST-01" in codes

    deactivated = await ac.delete(f"/api/v1/customers/{customer['id']}", headers=headers)
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["data"]["status"] == "inactive"

    active_only = await ac.get("/api/v1/customers?active_only=true", headers=headers)
    assert active_only.status_code == 200
    active_ids = {row["id"] for row in active_only.json()["data"]}
    assert customer["id"] not in active_ids


@pytest.mark.asyncio
async def test_pos_credit_rejects_walk_in_customer(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    walk = await ac.post(
        "/api/v1/customers",
        headers=mgr,
        json={"name": "Walk Credit Block", "party_type": "walk-in", "credit_limit": 500},
    )
    assert walk.status_code == 200, walk.text
    walk_id = walk.json()["data"]["id"]

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 20},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]

    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": session_id,
            "party_id": walk_id,
            "payment_method": "credit",
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert sale.status_code == 400
    assert "registered" in sale.json()["detail"].lower()
