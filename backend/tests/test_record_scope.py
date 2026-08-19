"""Record-level RBAC scope (own vs all)."""

from __future__ import annotations

import pyotp
import pytest

from app import models as m
from app import purchasing as purchasing_svc
from app import sales as sales_svc
from app import sales_docs as sales_docs_svc
from app.expenses import create_expense, ensure_default_categories
from app.rbac import (
    RECORD_SCOPE_KEY,
    assert_record_access,
    record_scope_for_claims,
    record_scope_from_permissions,
)
from tests.conftest import auth_headers


async def _admin_headers(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_record_scope_defaults_and_override():
    assert record_scope_from_permissions("cashier", None) == "own"
    assert record_scope_from_permissions("store_manager", None) == "all"
    assert record_scope_from_permissions("cashier", {RECORD_SCOPE_KEY: "all"}) == "all"
    assert record_scope_for_claims({"role": "sales_officer", "permissions": {}}) == "own"


def test_assert_record_access_own_hides_foreign():
    claims = {"role": "cashier", "sub": "u1", "permissions": {RECORD_SCOPE_KEY: "own"}}
    assert_record_access(claims, "u1")
    with pytest.raises(Exception) as exc:
        assert_record_access(claims, "u2")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_expense_own_scope_hides_others_records(client, db_session):
    ac, seed = client
    admin = await _admin_headers(ac, seed)
    await ensure_default_categories(db_session, seed["t1"].id)
    await db_session.commit()

    foreign = await create_expense(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["admin1"].id,
        amount=40,
        description="Admin expense",
        category="Utilities",
        payment_method="cash",
    )
    await db_session.commit()

    # Restrict store manager to own records
    patched = await ac.patch(
        f"/api/v1/users/{seed['mgr1'].id}",
        headers=admin,
        json={"record_scope": "own"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["record_scope"] == "own"

    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    missing = await ac.get(f"/api/v1/expenses/{foreign.id}", headers=mgr)
    assert missing.status_code == 404

    listed = await ac.get("/api/v1/expenses", headers=mgr)
    assert listed.status_code == 200
    ids = {row["id"] for row in listed.json()["data"]}
    assert foreign.id not in ids

    created = await ac.post(
        "/api/v1/expenses",
        headers=mgr,
        json={"amount": 12, "description": "Mine", "category": "Supplies", "payment_method": "cash"},
    )
    assert created.status_code == 200, created.text
    mine_id = created.json()["data"]["id"]
    ok = await ac.get(f"/api/v1/expenses/{mine_id}", headers=mgr)
    assert ok.status_code == 200

    # Admin with default all still sees foreign expense
    admin2 = await _admin_headers(ac, seed)
    still = await ac.get(f"/api/v1/expenses/{foreign.id}", headers=admin2)
    assert still.status_code == 200


@pytest.mark.asyncio
async def test_roles_catalog_includes_record_scope(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/roles", headers=headers)
    assert r.status_code == 200
    by_role = {row["role"]: row for row in r.json()["data"]}
    assert by_role["cashier"]["record_scope"] == "own"
    assert by_role["accountant"]["record_scope"] == "all"


@pytest.mark.asyncio
async def test_sales_docs_own_scope_hides_others_records(client, db_session):
    ac, seed = client
    admin = await _admin_headers(ac, seed)

    foreign_quote = await sales_docs_svc.create_quotation(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["admin1"].id,
        customer_id=seed["party1"].id,
        items=[{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 8}],
    )
    foreign_order = await sales_docs_svc.create_order(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["admin1"].id,
        customer_id=seed["party1"].id,
        items=[{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 8}],
    )
    invoice = await sales_svc.create_sales_invoice(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["admin1"].id,
        customer_id=seed["party1"].id,
        items=[{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 8}],
    )
    invoice = await sales_svc.post_sales_invoice(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["admin1"].id,
        invoice_id=invoice.id,
    )
    foreign_return = await sales_docs_svc.create_return(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["admin1"].id,
        sales_invoice_id=invoice.id,
        items=[{"product_id": seed["p1"].id, "quantity": 1}],
    )
    await db_session.commit()

    patched = await ac.patch(
        f"/api/v1/users/{seed['mgr1'].id}",
        headers=admin,
        json={"record_scope": "own"},
    )
    assert patched.status_code == 200, patched.text

    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    assert (await ac.get(f"/api/v1/sales/quotations/{foreign_quote.id}", headers=mgr)).status_code == 404
    assert (await ac.get(f"/api/v1/sales/orders/{foreign_order.id}", headers=mgr)).status_code == 404
    assert (await ac.get(f"/api/v1/sales/returns/{foreign_return.id}", headers=mgr)).status_code == 404
    assert (await ac.post(f"/api/v1/sales/quotations/{foreign_quote.id}/accept", headers=mgr)).status_code == 404
    assert (await ac.post(f"/api/v1/sales/orders/{foreign_order.id}/confirm", headers=mgr)).status_code == 404

    q_list = await ac.get("/api/v1/sales/quotations", headers=mgr)
    assert q_list.status_code == 200
    assert foreign_quote.id not in {row["id"] for row in q_list.json()["data"]}

    o_list = await ac.get("/api/v1/sales/orders", headers=mgr)
    assert o_list.status_code == 200
    assert foreign_order.id not in {row["id"] for row in o_list.json()["data"]}

    r_list = await ac.get("/api/v1/sales/returns", headers=mgr)
    assert r_list.status_code == 200
    assert foreign_return.id not in {row["id"] for row in r_list.json()["data"]}

    mine_q = await ac.post(
        "/api/v1/sales/quotations",
        headers=mgr,
        json={
            "customer_id": seed["party1"].id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 3}],
        },
    )
    assert mine_q.status_code == 200, mine_q.text
    mine_qid = mine_q.json()["data"]["id"]
    assert (await ac.get(f"/api/v1/sales/quotations/{mine_qid}", headers=mgr)).status_code == 200

    # Creating a return against someone else's invoice is hidden under own-scope
    blocked_return = await ac.post(
        "/api/v1/sales/returns",
        headers=mgr,
        json={
            "sales_invoice_id": invoice.id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert blocked_return.status_code == 404

    # Admin with default all still sees foreign docs
    admin2 = await _admin_headers(ac, seed)
    assert (await ac.get(f"/api/v1/sales/quotations/{foreign_quote.id}", headers=admin2)).status_code == 200
    assert (await ac.get(f"/api/v1/sales/orders/{foreign_order.id}", headers=admin2)).status_code == 200
    assert (await ac.get(f"/api/v1/sales/returns/{foreign_return.id}", headers=admin2)).status_code == 200


@pytest.mark.asyncio
async def test_purchasing_docs_own_scope_hides_others_records(client, db_session):
    ac, seed = client
    admin = await _admin_headers(ac, seed)

    supplier = m.Party(
        tenant_id=seed["t1"].id,
        kind="supplier",
        name="Scope Supplier",
        status="active",
    )
    db_session.add(supplier)
    await db_session.flush()

    foreign_pr = await purchasing_svc.create_purchase_request(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["admin1"].id,
        supplier_id=supplier.id,
        items=[{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 4}],
    )
    foreign_po = await purchasing_svc.create_purchase_order(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["admin1"].id,
        supplier_id=supplier.id,
        items=[{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 4}],
    )
    foreign_inv = await purchasing_svc.create_purchase_invoice(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["admin1"].id,
        supplier_id=supplier.id,
        items=[{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 4}],
    )
    await db_session.commit()

    patched = await ac.patch(
        f"/api/v1/users/{seed['mgr1'].id}",
        headers=admin,
        json={"record_scope": "own"},
    )
    assert patched.status_code == 200, patched.text
    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    assert (await ac.get(f"/api/v1/purchasing/requests/{foreign_pr.id}", headers=mgr)).status_code == 404
    assert (await ac.get(f"/api/v1/purchasing/orders/{foreign_po.id}", headers=mgr)).status_code == 404
    assert (await ac.get(f"/api/v1/purchasing/invoices/{foreign_inv.id}", headers=mgr)).status_code == 404
    assert (await ac.post(f"/api/v1/purchasing/orders/{foreign_po.id}/send", headers=mgr)).status_code == 404
    assert (await ac.post(f"/api/v1/purchasing/requests/{foreign_pr.id}/submit", headers=mgr)).status_code == 404

    pr_list = await ac.get("/api/v1/purchasing/requests", headers=mgr)
    assert pr_list.status_code == 200
    assert foreign_pr.id not in {row["id"] for row in pr_list.json()["data"]}
    po_list = await ac.get("/api/v1/purchasing/orders", headers=mgr)
    assert po_list.status_code == 200
    assert foreign_po.id not in {row["id"] for row in po_list.json()["data"]}
    inv_list = await ac.get("/api/v1/purchasing/invoices", headers=mgr)
    assert inv_list.status_code == 200
    assert foreign_inv.id not in {row["id"] for row in inv_list.json()["data"]}

    # Approvals intentionally bypass own-scope (creator is admin1, not mgr)
    await purchasing_svc.submit_purchase_request(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["admin1"].id,
        request_id=foreign_pr.id,
    )
    await db_session.commit()
    approved = await ac.post(
        f"/api/v1/purchasing/requests/{foreign_pr.id}/approve",
        headers=mgr,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["status"] == "approved"

    mine_po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=mgr,
        json={
            "supplier_id": supplier.id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 3}],
        },
    )
    assert mine_po.status_code == 200, mine_po.text
    mine_id = mine_po.json()["data"]["id"]
    assert (await ac.get(f"/api/v1/purchasing/orders/{mine_id}", headers=mgr)).status_code == 200

    admin2 = await _admin_headers(ac, seed)
    assert (await ac.get(f"/api/v1/purchasing/orders/{foreign_po.id}", headers=admin2)).status_code == 200
    assert (await ac.get(f"/api/v1/purchasing/requests/{foreign_pr.id}", headers=admin2)).status_code == 200
