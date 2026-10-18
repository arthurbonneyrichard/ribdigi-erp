"""Close retail audit gaps: multi-line PR, POS hides inactive, GRN double stock."""

from __future__ import annotations

from uuid import uuid4

import pyotp
import pytest

from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _officer(db_session, seed, email: str):
    user = m.User(
        tenant_id=seed["t1"].id,
        email=email,
        full_name="Audit officer",
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
async def test_multiline_purchase_request_converts_to_po(client, db_session):
    ac, seed = client
    email = f"io-pr2-{uuid4().hex[:6]}@alpha.example.com"
    await _officer(db_session, seed, email)
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email=email, tenant_slug="alpha")
    second = await ac.post(
        "/api/v1/products",
        headers=admin,
        json={"name": f"PR line B {uuid4().hex[:6]}", "selling_price": 4},
    )
    assert second.status_code == 200, second.text
    second_id = second.json()["data"]["id"]
    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": f"PR Vendor {uuid4().hex[:6]}", "email": f"prv-{uuid4().hex[:6]}@example.com"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    created = await ac.post(
        "/api/v1/purchasing/requests",
        headers=io,
        json={
            "preferred_supplier_id": supplier_id,
            "items": [
                {"product_id": seed["p1"].id, "quantity": 3},
                {"product_id": second_id, "quantity": 5},
            ],
        },
    )
    assert created.status_code == 200, created.text
    req = created.json()["data"]
    assert len(req["items"]) == 2
    rid = req["id"]

    submitted = await ac.post(
        f"/api/v1/purchasing/requests/{rid}/submit", headers=io, json={}
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["data"]["status"] == "pending"

    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    l1 = await ac.post(
        f"/api/v1/purchasing/requests/{rid}/approve", headers=mgr, json={}
    )
    assert l1.status_code == 200, l1.text
    l2 = await ac.post(
        f"/api/v1/purchasing/requests/{rid}/approve", headers=admin, json={}
    )
    assert l2.status_code == 200, l2.text
    assert l2.json()["data"]["status"] == "approved"

    converted = await ac.post(
        f"/api/v1/purchasing/requests/{rid}/convert",
        headers=io,
        json={"supplier_id": supplier_id},
    )
    assert converted.status_code == 200, converted.text
    body = converted.json()["data"]
    po = body.get("purchase_order") or body
    items = po.get("items") or []
    assert len(items) == 2
    by_product = {row["product_id"]: row["quantity"] for row in items}
    assert by_product[seed["p1"].id] == 3.0
    assert by_product[second_id] == 5.0


@pytest.mark.asyncio
async def test_inactive_product_hidden_from_pos_search(client, db_session):
    ac, seed = client
    admin = await _super(ac, seed)
    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    name = f"HideMe {uuid4().hex[:6]}"
    created = await ac.post(
        "/api/v1/products",
        headers=admin,
        json={"name": name, "selling_price": 9, "stock_qty": 5},
    )
    assert created.status_code == 200, created.text
    pid = created.json()["data"]["id"]

    found = await ac.get(f"/api/v1/pos/products/search?q={name}", headers=cashier)
    assert found.status_code == 200, found.text
    assert pid in {row["id"] for row in found.json()["data"]}

    deact = await ac.patch(
        f"/api/v1/products/{pid}",
        headers=admin,
        json={"is_active": False},
    )
    assert deact.status_code == 200, deact.text

    hidden = await ac.get(f"/api/v1/pos/products/search?q={name}", headers=cashier)
    assert hidden.status_code == 200, hidden.text
    assert pid not in {row["id"] for row in hidden.json()["data"]}


@pytest.mark.asyncio
async def test_identical_grn_retry_does_not_double_stock(client, db_session):
    ac, seed = client
    email = f"io-dbl-{uuid4().hex[:6]}@alpha.example.com"
    await _officer(db_session, seed, email)
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email=email, tenant_slug="alpha")
    product = await db_session.get(m.Product, seed["p1"].id)
    stock_before = float(product.stock_qty or 0)

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": f"Dbl GRN {uuid4().hex[:6]}", "email": f"dbl-{uuid4().hex[:6]}@example.com"},
    )
    assert supplier.status_code == 200, supplier.text
    po_resp = await ac.post(
        "/api/v1/purchasing/orders",
        headers=io,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "items": [{"product_id": seed["p1"].id, "quantity": 6, "unit_price": 2}],
        },
    )
    assert po_resp.status_code == 200, po_resp.text
    po = po_resp.json()["data"]
    row = await db_session.get(m.PurchaseOrder, po["id"])
    row.status = "sent"
    await db_session.commit()

    payload = {
        "purchase_order_id": po["id"],
        "items": [
            {
                "po_item_id": po["items"][0]["id"],
                "received_qty": 6,
                "accepted_qty": 6,
            }
        ],
    }
    first = await ac.post("/api/v1/purchasing/grn", headers=io, json=payload)
    assert first.status_code == 200, first.text
    await db_session.refresh(product)
    after_first = float(product.stock_qty or 0)
    assert after_first == pytest.approx(stock_before + 6.0)

    retry = await ac.post("/api/v1/purchasing/grn", headers=io, json=payload)
    assert retry.status_code == 409, retry.text
    await db_session.refresh(product)
    assert float(product.stock_qty or 0) == pytest.approx(after_first)
