"""Store membership must gate mutating sales/inventory/POS/purchase/export writes.

Empty memberships = grandfather (all stores). Assigned memberships must be
enforced even when require_active_store only checks tenant + active flag.
"""

from __future__ import annotations

import pyotp
import pytest

from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _cashier(ac):
    return await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")


async def _two_stores_and_warehouses(ac, admin):
    a = await ac.post(
        "/api/v1/stores", headers=admin, json={"code": "SMA", "name": "Store Alpha"}
    )
    b = await ac.post(
        "/api/v1/stores", headers=admin, json={"code": "SMB", "name": "Store Bravo"}
    )
    assert a.status_code == 200, a.text
    assert b.status_code == 200, b.text
    store_a = a.json()["data"]["id"]
    store_b = b.json()["data"]["id"]
    wa = await ac.post(
        "/api/v1/warehouses",
        headers=admin,
        json={"code": "WHA", "name": "WH Alpha", "store_id": store_a},
    )
    wb = await ac.post(
        "/api/v1/warehouses",
        headers=admin,
        json={"code": "WHB", "name": "WH Bravo", "store_id": store_b},
    )
    assert wa.status_code == 200, wa.text
    assert wb.status_code == 200, wb.text
    return store_a, store_b, wa.json()["data"]["id"], wb.json()["data"]["id"]


@pytest.mark.asyncio
async def test_empty_membership_grandfathers_all_stores_for_pos(client):
    ac, seed = client
    admin = await _admin(ac, seed)
    cashier = await _cashier(ac)
    store_a, store_b, _wh_a, _wh_b = await _two_stores_and_warehouses(ac, admin)

    listed = await ac.get(f"/api/v1/users/{seed['u1'].id}/stores", headers=admin)
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"]["all_stores"] is True

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cashier,
        json={"opening_cash": 0, "store_id": store_b},
    )
    assert opened.status_code == 200, opened.text


@pytest.mark.asyncio
async def test_membership_blocks_other_store_pos_sales_inventory_export(client):
    ac, seed = client
    admin = await _admin(ac, seed)
    mgr = await _mgr(ac)
    cashier = await _cashier(ac)
    store_a, store_b, wh_a, wh_b = await _two_stores_and_warehouses(ac, admin)

    assign_mgr = await ac.put(
        f"/api/v1/users/{seed['mgr1'].id}/stores",
        headers=admin,
        json={"store_ids": [store_a]},
    )
    assert assign_mgr.status_code == 200, assign_mgr.text
    assert assign_mgr.json()["data"]["all_stores"] is False

    assign_c = await ac.put(
        f"/api/v1/users/{seed['u1'].id}/stores",
        headers=admin,
        json={"store_ids": [store_a]},
    )
    assert assign_c.status_code == 200, assign_c.text

    denied_pos = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cashier,
        json={"opening_cash": 0, "store_id": store_b},
    )
    assert denied_pos.status_code == 403, denied_pos.text
    assert denied_pos.json()["detail"]["code"] == "STORE_ACCESS_DENIED"

    allowed_pos = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cashier,
        json={"opening_cash": 0, "store_id": store_a},
    )
    assert allowed_pos.status_code == 200, allowed_pos.text

    inv_body = {
        "customer_id": seed["party1"].id,
        "store_id": store_b,
        "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 2}],
    }
    denied_inv = await ac.post("/api/v1/sales/invoices", headers=mgr, json=inv_body)
    assert denied_inv.status_code == 403, denied_inv.text

    inv_body["store_id"] = store_a
    ok_inv = await ac.post("/api/v1/sales/invoices", headers=mgr, json=inv_body)
    assert ok_inv.status_code == 200, ok_inv.text

    denied_adj = await ac.post(
        f"/api/v1/inventory/adjust/{seed['p1'].id}",
        headers=mgr,
        json={"quantity": -1, "reason": "damage", "warehouse_id": wh_b},
    )
    assert denied_adj.status_code == 403, denied_adj.text

    ok_adj = await ac.post(
        f"/api/v1/inventory/adjust/{seed['p1'].id}",
        headers=mgr,
        json={"quantity": 1, "reason": "found", "warehouse_id": wh_a},
    )
    assert ok_adj.status_code == 200, ok_adj.text

    denied_exp = await ac.post(
        "/api/v1/expenses",
        headers=mgr,
        json={"amount": 5, "description": "Store B tea", "category": "misc", "store_id": store_b},
    )
    assert denied_exp.status_code == 403, denied_exp.text

    denied_export = await ac.get(
        "/api/v1/reports/export",
        headers=mgr,
        params={"report_type": "sales_by_store", "store_id": store_b},
    )
    assert denied_export.status_code == 403, denied_export.text

    ok_export = await ac.get(
        "/api/v1/reports/export",
        headers=mgr,
        params={"report_type": "sales_by_store", "store_id": store_a},
    )
    assert ok_export.status_code == 200, ok_export.text

    # Privileged company admin still writes any store.
    admin_tenant = await auth_headers(
        ac, email="admin@alpha.example.com", tenant_slug="alpha"
    )
    admin_pos = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=admin_tenant,
        json={"opening_cash": 0, "store_id": store_b},
    )
    assert admin_pos.status_code == 200, admin_pos.text


@pytest.mark.asyncio
async def test_grn_blocked_for_unassigned_warehouse(client):
    ac, seed = client
    admin = await _admin(ac, seed)
    store_a, store_b, wh_a, wh_b = await _two_stores_and_warehouses(ac, admin)

    created = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": "invoff@alpha.example.com",
            "password": "SecurePass123!",
            "full_name": "Inv Officer",
            "role": "inventory_officer",
        },
    )
    assert created.status_code == 200, created.text
    officer_id = created.json()["data"]["id"]
    assign = await ac.put(
        f"/api/v1/users/{officer_id}/stores",
        headers=admin,
        json={"store_ids": [store_a]},
    )
    assert assign.status_code == 200, assign.text

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "Membership Supplier", "email": "msup@example.com"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=admin,
        json={
            "supplier_id": supplier_id,
            "warehouse_id": wh_b,
            "items": [{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 1}],
        },
    )
    assert po.status_code == 200, po.text
    po_id = po.json()["data"]["id"]
    sent = await ac.post(f"/api/v1/purchasing/orders/{po_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    po_item_id = sent.json()["data"]["items"][0]["id"]

    officer = await auth_headers(
        ac, email="invoff@alpha.example.com", tenant_slug="alpha"
    )
    denied = await ac.post(
        "/api/v1/purchasing/grn",
        headers=officer,
        json={
            "purchase_order_id": po_id,
            "warehouse_id": wh_b,
            "items": [
                {
                    "po_item_id": po_item_id,
                    "received_qty": 1,
                    "accepted_qty": 1,
                }
            ],
        },
    )
    assert denied.status_code == 403, denied.text

    po_a = await ac.post(
        "/api/v1/purchasing/orders",
        headers=admin,
        json={
            "supplier_id": supplier_id,
            "warehouse_id": wh_a,
            "items": [{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 1}],
        },
    )
    assert po_a.status_code == 200, po_a.text
    sent_a = await ac.post(
        f"/api/v1/purchasing/orders/{po_a.json()['data']['id']}/send", headers=admin
    )
    assert sent_a.status_code == 200, sent_a.text
    allowed = await ac.post(
        "/api/v1/purchasing/grn",
        headers=officer,
        json={
            "purchase_order_id": po_a.json()["data"]["id"],
            "warehouse_id": wh_a,
            "items": [
                {
                    "po_item_id": sent_a.json()["data"]["items"][0]["id"],
                    "received_qty": 1,
                    "accepted_qty": 1,
                }
            ],
        },
    )
    assert allowed.status_code == 200, allowed.text


@pytest.mark.asyncio
async def test_spoofed_tenant_guessed_id_and_body_tenant(client):
    ac, seed = client
    admin = await _admin(ac, seed)
    mgr = await _mgr(ac)
    store_a, store_b, _wh_a, _wh_b = await _two_stores_and_warehouses(ac, admin)
    await ac.put(
        f"/api/v1/users/{seed['mgr1'].id}/stores",
        headers=admin,
        json={"store_ids": [store_a]},
    )

    spoof = dict(mgr)
    spoof["X-Tenant-ID"] = seed["t2"].id
    r = await ac.post(
        "/api/v1/sales/invoices",
        headers=spoof,
        json={
            "customer_id": seed["party1"].id,
            "store_id": store_a,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 2}],
        },
    )
    assert r.status_code == 403, r.text

    guessed = await ac.post(
        "/api/v1/sales/invoices",
        headers=mgr,
        json={
            "customer_id": seed["party1"].id,
            "store_id": "00000000-0000-4000-8000-000000000099",
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 2}],
        },
    )
    assert guessed.status_code == 404, guessed.text

    extra = await ac.post(
        "/api/v1/sales/invoices",
        headers=mgr,
        json={
            "customer_id": seed["party1"].id,
            "tenant_id": seed["t2"].id,
            "store_id": store_a,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 2}],
        },
    )
    assert extra.status_code == 422, extra.text

    cashier = await _cashier(ac)
    missing = await ac.post(
        "/api/v1/sales/invoices",
        headers=cashier,
        json={
            "customer_id": seed["party1"].id,
            "store_id": store_a,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 2}],
        },
    )
    assert missing.status_code == 403, missing.text
