"""Low-stock notifications target inventory_officer + store_manager (BR-5.5)."""

from __future__ import annotations

import pytest

from app import emailer
from app import models as m
from app import notifications as note_svc
from app.rbac import permissions_for_role
from app.security import hash_password


def _outbox_recipients() -> set[str]:
    out: set[str] = set()
    for row in emailer.get_dev_outbox():
        to = row.get("to")
        if isinstance(to, list):
            out.update(str(x) for x in to)
        elif to:
            out.add(str(to))
    return out


@pytest.mark.asyncio
async def test_low_stock_emails_inventory_officer_and_store_manager(
    db_session, seeded, monkeypatch
):
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")
    emailer.clear_dev_outbox()

    tenant_id = seeded["t1"].id
    inv = m.User(
        tenant_id=tenant_id,
        email="inventory@alpha.example.com",
        full_name="Inventory Officer",
        password_hash=hash_password("SecurePass123!"),
        role="inventory_officer",
        email_verified=True,
        is_active=True,
        permissions=permissions_for_role("inventory_officer"),
    )
    db_session.add(inv)
    await db_session.flush()

    product = seeded["p1"]
    product.stock_qty = 2
    product.reorder_level = 10
    await db_session.flush()

    note = await note_svc.notify_low_stock_if_needed(
        db_session, tenant_id=tenant_id, product=product
    )
    assert note is not None
    assert note.category == "low_stock"
    assert note.entity_id == product.id

    recipients = _outbox_recipients()
    assert "inventory@alpha.example.com" in recipients
    assert "mgr@alpha.example.com" in recipients
    assert "admin@alpha.example.com" in recipients
    # Cashiers are not low-stock notify roles
    assert "cashier@alpha.example.com" not in recipients
    assert all("Low Stock" in (m.get("subject") or "") for m in emailer.get_dev_outbox())


@pytest.mark.asyncio
async def test_warehouse_low_stock_emails_roles(db_session, seeded, monkeypatch):
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")
    emailer.clear_dev_outbox()

    tenant_id = seeded["t1"].id
    store = m.Store(tenant_id=tenant_id, name="LS WH Store", code="LS-S", is_active=True)
    db_session.add(store)
    await db_session.flush()
    wh = m.Warehouse(
        tenant_id=tenant_id, store_id=store.id, name="LS WH", code="LS-WH"
    )
    db_session.add(wh)
    await db_session.flush()

    product = seeded["p1"]
    stock = m.WarehouseStock(
        tenant_id=tenant_id,
        warehouse_id=wh.id,
        product_id=product.id,
        quantity=1,
        reorder_level=5,
        reorder_qty=20,
    )
    db_session.add(stock)
    await db_session.flush()

    note = await note_svc.notify_warehouse_low_stock_if_needed(
        db_session, tenant_id=tenant_id, product=product, stock=stock
    )
    assert note is not None
    assert note.entity_type == "warehouse_stock"
    recipients = _outbox_recipients()
    assert "mgr@alpha.example.com" in recipients
    assert "admin@alpha.example.com" in recipients
    assert "cashier@alpha.example.com" not in recipients
    assert any("Store/warehouse low stock" in (m.get("subject") or "") for m in emailer.get_dev_outbox())
