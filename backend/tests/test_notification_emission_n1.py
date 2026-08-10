"""Stage 16 N1: notification emission proof matrix (low stock / sales / credit / operational)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import models as m
from app import notifications as notifications_svc
from app.inventory import apply_stock_change
from app.notifications import update_preferences
from app.rbac import permissions_for_role
from app.security import hash_password
from app.stores import create_store
from tests.conftest import auth_headers


async def _cashier(ac):
    return await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_low_stock_scan_emits_and_lists_in_stock_group(client, db_session):
    """Low Stock bucket: scan_low_stock creates unread low_stock; visible via HTTP."""
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id

    product = m.Product(
        tenant_id=tenant_id,
        name="S16 N1 Low Stock SKU",
        sku="S16-N1-LOW",
        cost_price=1,
        selling_price=2,
        stock_qty=3,
        reorder_level=10,
        minimum_stock=1,
    )
    db_session.add(product)
    await db_session.commit()
    product_id = product.id

    created = await notifications_svc.scan_low_stock(db_session, tenant_id)
    await db_session.commit()
    assert created >= 1

    notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == tenant_id,
                m.Notification.category == "low_stock",
                m.Notification.entity_id == product_id,
            )
        )
    ).scalars().all()
    assert len(notes) == 1
    assert notes[0].status == "unread"
    assert "S16 N1 Low Stock SKU" in notes[0].message

    listed = await ac.get("/api/v1/notifications?group=stock", headers=headers)
    assert listed.status_code == 200, listed.text
    rows = [n for n in listed.json()["data"] if n.get("entity_id") == product_id]
    assert len(rows) == 1
    assert rows[0]["category"] == "low_stock"
    assert rows[0].get("group") == "stock"

    # Idempotent: unread duplicate not recreated
    again = await notifications_svc.scan_low_stock(db_session, tenant_id)
    await db_session.commit()
    assert again == 0 or again >= 0  # other products may still create
    dupes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == tenant_id,
                m.Notification.category == "low_stock",
                m.Notification.entity_id == product_id,
            )
        )
    ).scalars().all()
    assert len(dupes) == 1


@pytest.mark.asyncio
async def test_new_order_emits_important_sales_event(client, db_session):
    """Important Sales Events bucket: sales order create → new_order."""
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id

    created = await ac.post(
        "/api/v1/sales/orders",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 1,
                    "unit_price": 12,
                    "tax_rate": 0,
                    "discount": 0,
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    order = created.json()["data"]
    order_id = order["id"]

    notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == tenant_id,
                m.Notification.category == "new_order",
                m.Notification.entity_id == order_id,
            )
        )
    ).scalars().all()
    assert len(notes) >= 1
    assert "New sales order" in notes[0].title

    listed = await ac.get("/api/v1/notifications?group=orders", headers=headers)
    assert listed.status_code == 200
    cats = {n["category"] for n in listed.json()["data"] if n.get("entity_id") == order_id}
    assert "new_order" in cats


@pytest.mark.asyncio
async def test_credit_limit_alert_on_invoice_post(client, db_session):
    """Credit Alerts bucket: invoice post at ≥80% utilization → credit_limit."""
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    product = m.Product(
        tenant_id=tenant_id,
        name="S16 N1 Credit SKU",
        sku="S16-N1-CR",
        cost_price=1,
        selling_price=100,
        stock_qty=0,
        tax_exempt=True,
    )
    db_session.add(product)
    await db_session.flush()
    await apply_stock_change(
        db_session,
        tenant_id=tenant_id,
        product_id=product.id,
        quantity_delta=20,
        movement_type="stock_in",
        user_id=seed["mgr1"].id,
    )
    await db_session.commit()

    customer = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={
            "name": "S16 N1 Credit Cust",
            "email": "s16-n1-credit@example.com",
            "party_type": "registered",
            "credit_limit": 1000,
        },
    )
    assert customer.status_code == 200, customer.text
    customer_id = customer.json()["data"]["id"]

    # 9 × 100 = 900 → 90% of 1000 credit limit
    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [
                {
                    "product_id": product.id,
                    "quantity": 9,
                    "unit_price": 100,
                    "tax_rate": 0,
                    "discount": 0,
                }
            ],
        },
    )
    assert inv.status_code == 200, inv.text
    invoice_id = inv.json()["data"]["id"]
    assert float(inv.json()["data"]["total_amount"]) == pytest.approx(900)

    posted = await ac.post(f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers)
    assert posted.status_code == 200, posted.text

    notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == tenant_id,
                m.Notification.category == "credit_limit",
                m.Notification.entity_id == customer_id,
            )
        )
    ).scalars().all()
    assert len(notes) >= 1
    assert "Credit Limit Warning" in notes[0].title
    assert "90%" in notes[0].message or "0.9" in notes[0].message or "900" in notes[0].message

    listed = await ac.get("/api/v1/notifications?group=payments", headers=headers)
    assert listed.status_code == 200
    assert any(
        n["category"] == "credit_limit" and n.get("entity_id") == customer_id
        for n in listed.json()["data"]
    )


@pytest.mark.asyncio
async def test_purchase_received_on_grn_post(client, db_session):
    """Operational Alerts: GRN post → purchase_received."""
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id
    product = seed["p1"]
    product.stock_qty = 0
    await db_session.commit()

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "S16 N1 GRN Sup"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [
                {
                    "product_id": str(product.id),
                    "quantity": 4,
                    "unit_price": 5,
                    "tax_rate": 0,
                    "discount": 0,
                }
            ],
        },
    )
    assert po.status_code == 200, po.text
    po_id = po.json()["data"]["id"]
    po_item_id = po.json()["data"]["items"][0]["id"]

    sent = await ac.post(f"/api/v1/purchasing/orders/{po_id}/send", headers=headers)
    assert sent.status_code == 200, sent.text

    grn = await ac.post(
        "/api/v1/purchasing/grn",
        headers=headers,
        json={
            "purchase_order_id": po_id,
            "items": [
                {
                    "po_item_id": po_item_id,
                    "received_qty": 4,
                    "accepted_qty": 4,
                    "rejected_qty": 0,
                }
            ],
        },
    )
    assert grn.status_code == 200, grn.text
    grn_id = grn.json()["data"]["id"]

    notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == tenant_id,
                m.Notification.category == "purchase_received",
                m.Notification.entity_id == grn_id,
            )
        )
    ).scalars().all()
    assert len(notes) >= 1
    assert "Purchase received" in notes[0].title

    listed = await ac.get(
        "/api/v1/notifications?category=purchase_received", headers=headers
    )
    assert listed.status_code == 200
    assert any(n.get("entity_id") == grn_id for n in listed.json()["data"])


@pytest.mark.asyncio
async def test_shift_variance_emits_and_honors_dashboard_pref(client, db_session):
    """Operational Alerts: POS close variance → shift_variance; prefs can suppress."""
    ac, seed = client
    headers = await _cashier(ac)
    tenant_id = seed["t1"].id
    cashier = seed["u1"]

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 100},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]

    closed = await ac.post(
        f"/api/v1/pos/sessions/{session_id}/close",
        headers=headers,
        json={"actual_cash": 90},  # expected 100 → variance -10
    )
    assert closed.status_code == 200, closed.text

    notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == tenant_id,
                m.Notification.category == "shift_variance",
                m.Notification.entity_id == session_id,
            )
        )
    ).scalars().all()
    assert len(notes) == 1
    assert notes[0].user_id == cashier.id
    assert "variance" in notes[0].message.lower()

    # Prefs: dashboard off → targeted create_notification skipped
    await update_preferences(
        db_session,
        tenant_id,
        cashier.id,
        {"shift_variance": {"dashboard": False, "email": False, "sms": False}},
    )
    await db_session.commit()

    opened2 = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 50},
    )
    assert opened2.status_code == 200, opened2.text
    session2 = opened2.json()["data"]["session_id"]

    closed2 = await ac.post(
        f"/api/v1/pos/sessions/{session2}/close",
        headers=headers,
        json={"actual_cash": 40},
    )
    assert closed2.status_code == 200, closed2.text

    skipped = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == tenant_id,
                m.Notification.category == "shift_variance",
                m.Notification.entity_id == session2,
            )
        )
    ).scalars().all()
    assert skipped == []


@pytest.mark.asyncio
async def test_transfer_ship_emits_operational_alert(client, db_session):
    """Operational Alerts: inter-store ship → transfer notification."""
    ac, seed = client
    tenant_id = seed["t1"].id
    mgr_from = seed["mgr1"]

    product = m.Product(
        tenant_id=tenant_id,
        name="S16 N1 Xfer SKU",
        sku="S16-N1-XFER",
        cost_price=1,
        selling_price=2,
        stock_qty=0,
    )
    db_session.add(product)
    await db_session.flush()

    mgr_to = m.User(
        tenant_id=tenant_id,
        email="mgr-s16-n1-dest@alpha.example.com",
        full_name="S16 N1 Dest",
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
        code="S16N1S",
        name="S16 N1 Src",
        manager_id=mgr_from.id,
    )
    to_store = await create_store(
        db_session,
        tenant_id=tenant_id,
        code="S16N1D",
        name="S16 N1 Dst",
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
    from_wh_id = from_wh.id
    from_store_id, to_store_id = from_store.id, to_store.id
    product_id = product.id

    await apply_stock_change(
        db_session,
        tenant_id=tenant_id,
        product_id=product_id,
        quantity_delta=15,
        movement_type="stock_in",
        user_id=mgr_from.id,
        warehouse_id=from_wh_id,
    )
    await db_session.commit()

    mgr_from_h = await _mgr(ac)
    created = await ac.post(
        "/api/v1/stores/transfers",
        headers=mgr_from_h,
        json={
            "from_store_id": from_store_id,
            "to_store_id": to_store_id,
            "submit": True,
            "items": [{"product_id": product_id, "quantity": 3}],
        },
    )
    assert created.status_code == 200, created.text
    transfer_id = created.json()["data"]["id"]

    shipped = await ac.post(
        f"/api/v1/stores/transfers/{transfer_id}/ship",
        headers=mgr_from_h,
    )
    assert shipped.status_code == 200, shipped.text

    notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == tenant_id,
                m.Notification.category == "transfer",
                m.Notification.entity_id == transfer_id,
            )
        )
    ).scalars().all()
    assert len(notes) >= 1
    assert "In Transit" in notes[0].title or "Transfer" in notes[0].title

    listed = await ac.get("/api/v1/notifications?group=stock", headers=mgr_from_h)
    assert listed.status_code == 200
    assert any(
        n["category"] == "transfer" and n.get("entity_id") == transfer_id
        for n in listed.json()["data"]
    )


def test_low_stock_job_registered_for_ops_scan():
    """Celery/admin job surface includes scan_low_stock (emission runner for Low Stock bucket)."""
    from app import jobs as jobs_svc

    assert "scan_low_stock" in jobs_svc.JOB_HANDLERS
