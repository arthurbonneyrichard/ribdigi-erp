"""Handbook goods-received quantities (training guide pp. 15–16 and 23).

Accepted quantity is the only quantity that increases stock. Rejected quantity
needs a reason and does not. Outstanding is ordered minus the physical receipt.
"""

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
        full_name="Handbook receiver",
        password_hash=hash_password("SecurePass123!"),
        role="inventory_officer",
        email_verified=True,
        permissions=permissions_for_role("inventory_officer"),
        totp_enabled=False,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _sent_po(ac, db_session, *, admin, io, seed, items: list[dict]):
    suffix = uuid4().hex[:8]
    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": f"Handbook Vendor {suffix}", "email": f"hb-{suffix}@example.com"},
    )
    assert supplier.status_code == 200, supplier.text
    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=io,
        json={"supplier_id": supplier.json()["data"]["id"], "items": items},
    )
    assert created.status_code == 200, created.text
    po = created.json()["data"]
    row = await db_session.get(m.PurchaseOrder, po["id"])
    row.status = "sent"
    await db_session.commit()
    return po


@pytest.mark.asyncio
async def test_handbook_rice_receipt_keeps_outstanding_and_stocks_accepted_only(client, db_session):
    """Page 16: ordered 100, delivered 90, accepted 87, rejected 3, outstanding 10."""
    ac, seed = client
    email = f"io-rice-{uuid4().hex[:6]}@alpha.example.com"
    await _officer(db_session, seed, email)
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email=email, tenant_slug="alpha")
    product = await db_session.get(m.Product, seed["p1"].id)
    stock_before = float(product.stock_qty or 0)
    po = await _sent_po(
        ac,
        db_session,
        admin=admin,
        io=io,
        seed=seed,
        items=[{"product_id": seed["p1"].id, "quantity": 100, "unit_price": 4}],
    )
    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=io,
        json={
            "purchase_order_id": po["id"],
            "items": [
                {
                    "po_item_id": po["items"][0]["id"],
                    "received_qty": 90,
                    "accepted_qty": 87,
                    "rejected_qty": 3,
                    "rejection_reason": "Torn bags",
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    line = grn.json()["data"]["items"][0]
    assert line["accepted_qty"] == 87.0
    assert line["rejected_qty"] == 3.0
    await db_session.refresh(product)
    assert float(product.stock_qty or 0) == pytest.approx(stock_before + 87.0)
    order = await ac.get(f"/api/v1/purchasing/orders/{po['id']}", headers=io)
    assert order.status_code == 200
    body = order.json()["data"]
    assert body["items"][0]["received_qty"] == 90.0
    assert body["items"][0]["outstanding_qty"] == 10.0
    assert body["status"] == "partially_received"

    rest = await ac.post(
        "/api/v1/purchasing/grn",
        headers=io,
        json={
            "purchase_order_id": po["id"],
            "items": [
                {
                    "po_item_id": po["items"][0]["id"],
                    "received_qty": 10,
                    "accepted_qty": 10,
                    "rejected_qty": 0,
                }
            ],
        },
    )
    assert rest.status_code == 200, rest.text
    await db_session.refresh(product)
    assert float(product.stock_qty or 0) == pytest.approx(stock_before + 97.0)
    closed = await ac.get(f"/api/v1/purchasing/orders/{po['id']}", headers=io)
    assert closed.json()["data"]["items"][0]["outstanding_qty"] == 0.0
    assert closed.json()["data"]["status"] == "received"


@pytest.mark.asyncio
async def test_handbook_shop_receive_accepts_17_of_20(client, db_session):
    """Page 23: order 20, receive 18, accept 17, reject 1 damaged."""
    ac, seed = client
    email = f"io-shop-{uuid4().hex[:6]}@alpha.example.com"
    await _officer(db_session, seed, email)
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email=email, tenant_slug="alpha")
    product = await db_session.get(m.Product, seed["p1"].id)
    stock_before = float(product.stock_qty or 0)
    po = await _sent_po(
        ac,
        db_session,
        admin=admin,
        io=io,
        seed=seed,
        items=[{"product_id": seed["p1"].id, "quantity": 20, "unit_price": 5}],
    )
    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=io,
        json={
            "purchase_order_id": po["id"],
            "items": [
                {
                    "po_item_id": po["items"][0]["id"],
                    "received_qty": 18,
                    "accepted_qty": 17,
                    "rejected_qty": 1,
                    "rejection_reason": "Damaged carton",
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    await db_session.refresh(product)
    assert float(product.stock_qty or 0) == pytest.approx(stock_before + 17.0)
    order = await ac.get(f"/api/v1/purchasing/orders/{po['id']}", headers=io)
    body = order.json()["data"]
    assert body["items"][0]["outstanding_qty"] == 2.0
    assert body["status"] == "partially_received"


@pytest.mark.asyncio
async def test_purchase_return_posts_every_accepted_line(client, db_session):
    ac, seed = client
    email = f"io-ret-{uuid4().hex[:6]}@alpha.example.com"
    await _officer(db_session, seed, email)
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email=email, tenant_slug="alpha")
    second = await ac.post(
        "/api/v1/products",
        headers=admin,
        json={"name": f"Handbook second {uuid4().hex[:6]}", "selling_price": 3},
    )
    assert second.status_code == 200, second.text
    second_id = second.json()["data"]["id"]
    po = await _sent_po(
        ac,
        db_session,
        admin=admin,
        io=io,
        seed=seed,
        items=[
            {"product_id": seed["p1"].id, "quantity": 4, "unit_price": 2},
            {"product_id": second_id, "quantity": 6, "unit_price": 3},
        ],
    )
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
                },
                {
                    "po_item_id": po["items"][1]["id"],
                    "received_qty": 6,
                    "accepted_qty": 6,
                },
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    lines = grn.json()["data"]["items"]
    assert len(lines) == 2
    created = await ac.post(
        "/api/v1/purchasing/returns",
        headers=io,
        json={
            "goods_receipt_id": grn.json()["data"]["id"],
            "reason": "damaged",
            "items": [
                {"goods_receipt_item_id": lines[0]["id"], "quantity": 1},
                {"goods_receipt_item_id": lines[1]["id"], "quantity": 2},
            ],
        },
    )
    assert created.status_code == 200, created.text
    returned = created.json()["data"]["items"]
    assert len(returned) == 2
    assert {row["quantity"] for row in returned} == {1.0, 2.0}

    over = await ac.post(
        "/api/v1/purchasing/returns",
        headers=io,
        json={
            "goods_receipt_id": grn.json()["data"]["id"],
            "reason": "damaged",
            "items": [{"goods_receipt_item_id": lines[0]["id"], "quantity": 4}],
        },
    )
    assert over.status_code == 409, over.text


@pytest.mark.asyncio
async def test_po_amend_keeps_every_product_line(client, db_session):
    ac, seed = client
    email = f"io-amend-{uuid4().hex[:6]}@alpha.example.com"
    await _officer(db_session, seed, email)
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email=email, tenant_slug="alpha")
    second = await ac.post(
        "/api/v1/products",
        headers=admin,
        json={"name": f"Handbook amend {uuid4().hex[:6]}", "selling_price": 4},
    )
    assert second.status_code == 200, second.text
    second_id = second.json()["data"]["id"]
    po = await _sent_po(
        ac,
        db_session,
        admin=admin,
        io=io,
        seed=seed,
        items=[
            {"product_id": seed["p1"].id, "quantity": 10, "unit_price": 2},
            {"product_id": second_id, "quantity": 8, "unit_price": 3},
        ],
    )
    assert len(po["items"]) == 2
    amended = await ac.post(
        f"/api/v1/purchasing/orders/{po['id']}/amend",
        headers=io,
        json={
            "reason": "Supplier confirmed shortage",
            "items": [
                {"product_id": seed["p1"].id, "quantity": 7, "unit_price": 2},
                {"product_id": second_id, "quantity": 5, "unit_price": 3},
            ],
        },
    )
    assert amended.status_code == 200, amended.text
    lines = amended.json()["data"]["items"]
    assert len(lines) == 2
    by_product = {row["product_id"]: row["quantity"] for row in lines}
    assert by_product[seed["p1"].id] == 7.0
    assert by_product[second_id] == 5.0


@pytest.mark.asyncio
async def test_supplier_bill_from_grn_copies_every_accepted_line(client, db_session):
    ac, seed = client
    email = f"io-bill-{uuid4().hex[:6]}@alpha.example.com"
    await _officer(db_session, seed, email)
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email=email, tenant_slug="alpha")
    second = await ac.post(
        "/api/v1/products",
        headers=admin,
        json={"name": f"Handbook bill {uuid4().hex[:6]}", "selling_price": 5},
    )
    assert second.status_code == 200, second.text
    second_id = second.json()["data"]["id"]
    po = await _sent_po(
        ac,
        db_session,
        admin=admin,
        io=io,
        seed=seed,
        items=[
            {"product_id": seed["p1"].id, "quantity": 5, "unit_price": 2},
            {"product_id": second_id, "quantity": 3, "unit_price": 4},
        ],
    )
    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=io,
        json={
            "purchase_order_id": po["id"],
            "items": [
                {
                    "po_item_id": po["items"][0]["id"],
                    "received_qty": 5,
                    "accepted_qty": 4,
                    "rejected_qty": 1,
                    "rejection_reason": "Damaged unit",
                },
                {
                    "po_item_id": po["items"][1]["id"],
                    "received_qty": 3,
                    "accepted_qty": 3,
                },
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    grn_id = grn.json()["data"]["id"]
    bill = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=admin,
        json={"goods_receipt_id": grn_id},
    )
    assert bill.status_code == 200, bill.text
    items = bill.json()["data"]["items"]
    assert len(items) == 2
    by_product = {row["product_id"]: row["quantity"] for row in items}
    assert by_product[seed["p1"].id] == 4.0
    assert by_product[second_id] == 3.0

    duplicate = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=admin,
        json={"goods_receipt_id": grn_id},
    )
    assert duplicate.status_code == 409, duplicate.text


@pytest.mark.asyncio
async def test_supplier_bill_approve_and_pay_after_grn(client, db_session):
    """Handbook path: receive → bill → approve → supplier payment."""
    ac, seed = client
    email = f"io-pay-{uuid4().hex[:6]}@alpha.example.com"
    await _officer(db_session, seed, email)
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email=email, tenant_slug="alpha")
    po = await _sent_po(
        ac,
        db_session,
        admin=admin,
        io=io,
        seed=seed,
        items=[{"product_id": seed["p1"].id, "quantity": 5, "unit_price": 10}],
    )
    supplier_id = po["supplier_id"]
    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=io,
        json={
            "purchase_order_id": po["id"],
            "items": [
                {
                    "po_item_id": po["items"][0]["id"],
                    "received_qty": 5,
                    "accepted_qty": 5,
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    bill = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=admin,
        json={"goods_receipt_id": grn.json()["data"]["id"]},
    )
    assert bill.status_code == 200, bill.text
    inv = bill.json()["data"]
    assert inv["status"] == "draft"
    total = float(inv["total_amount"])
    assert total > 0

    approved = await ac.post(
        f"/api/v1/purchasing/invoices/{inv['id']}/approve",
        headers=admin,
        json={},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["status"] in {"unpaid", "overdue"}

    pay = await ac.post(
        f"/api/v1/suppliers/{supplier_id}/payments",
        headers=admin,
        json={
            "supplier_id": supplier_id,
            "purchase_invoice_id": inv["id"],
            "amount": total,
            "payment_method": "bank_transfer",
        },
    )
    assert pay.status_code == 200, pay.text
    assert float(pay.json()["data"]["amount"]) == pytest.approx(total)

    detail = await ac.get(f"/api/v1/purchasing/invoices/{inv['id']}", headers=admin)
    assert detail.status_code == 200, detail.text
    paid = detail.json()["data"]
    assert paid["status"] == "paid"
    assert float(paid.get("paid_amount") or 0) == pytest.approx(total)
    assert float(paid.get("balance_due") or 0) == pytest.approx(0)


@pytest.mark.asyncio
async def test_purchase_return_post_reduces_stock(client, db_session):
    """Posted return removes accepted stock (not draft-only)."""
    ac, seed = client
    email = f"io-postret-{uuid4().hex[:6]}@alpha.example.com"
    await _officer(db_session, seed, email)
    admin = await _super(ac, seed)
    io = await auth_headers(ac, email=email, tenant_slug="alpha")
    product = await db_session.get(m.Product, seed["p1"].id)
    po = await _sent_po(
        ac,
        db_session,
        admin=admin,
        io=io,
        seed=seed,
        items=[{"product_id": seed["p1"].id, "quantity": 8, "unit_price": 3}],
    )
    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=io,
        json={
            "purchase_order_id": po["id"],
            "items": [
                {
                    "po_item_id": po["items"][0]["id"],
                    "received_qty": 8,
                    "accepted_qty": 8,
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    await db_session.refresh(product)
    stock_after_grn = float(product.stock_qty or 0)
    grn_item_id = grn.json()["data"]["items"][0]["id"]

    created = await ac.post(
        "/api/v1/purchasing/returns",
        headers=io,
        json={
            "goods_receipt_id": grn.json()["data"]["id"],
            "reason": "damaged",
            "items": [{"goods_receipt_item_id": grn_item_id, "quantity": 3}],
        },
    )
    assert created.status_code == 200, created.text
    ret_id = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "draft"
    await db_session.refresh(product)
    assert float(product.stock_qty or 0) == pytest.approx(stock_after_grn)

    posted = await ac.post(
        f"/api/v1/purchasing/returns/{ret_id}/post",
        headers=admin,
        json={},
    )
    assert posted.status_code == 200, posted.text
    assert posted.json()["data"]["status"] == "posted"
    await db_session.refresh(product)
    assert float(product.stock_qty or 0) == pytest.approx(stock_after_grn - 3.0)
