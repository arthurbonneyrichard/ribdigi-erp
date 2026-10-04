"""Tenant-scoped low-stock scan leftover (notifications API + panel).

Celery / POST /jobs/scan_low_stock/run remains the all-tenant admin runner.
Store managers with notifications:write use POST /notifications/scan-low-stock.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


def test_notifications_panel_exposes_low_stock_scan_n1():
    page_path = None
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "frontend/app/notifications/page.tsx"
        if candidate.is_file():
            page_path = candidate
            break
    if page_path is None:
        pytest.skip("frontend sources are not mounted in this test environment")
    page = page_path.read_text(encoding="utf-8")
    assert "/notifications/scan-low-stock" in page
    assert "Scan low stock" in page
    assert "scanLowStock" in page


@pytest.mark.asyncio
async def test_scan_low_stock_http_emits_lists_and_stays_company_scoped(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    tid = seed["t1"].id
    cid = seed["c1"].id

    in_scope = m.Product(
        tenant_id=tid,
        company_id=cid,
        name="N1 Scan Low Stock SKU",
        sku="N1-SCAN-LOW",
        cost_price=1,
        selling_price=2,
        stock_qty=2,
        reorder_level=10,
        minimum_stock=1,
        is_active=True,
    )
    inactive = m.Product(
        tenant_id=tid,
        company_id=cid,
        name="N1 Inactive Low Stock",
        sku="N1-SCAN-INACTIVE",
        cost_price=1,
        selling_price=2,
        stock_qty=1,
        reorder_level=8,
        minimum_stock=1,
        is_active=False,
    )
    other_co = m.Company(
        tenant_id=tid,
        code="N1SCAN",
        name="N1 Other Company",
        industry="retail",
        is_active=True,
        is_default=False,
        store_limit=1,
    )
    db_session.add_all([in_scope, inactive, other_co])
    await db_session.flush()
    other_product = m.Product(
        tenant_id=tid,
        company_id=other_co.id,
        name="N1 Other Co Low Stock",
        sku="N1-SCAN-OTHER",
        cost_price=1,
        selling_price=2,
        stock_qty=1,
        reorder_level=9,
        minimum_stock=1,
        is_active=True,
    )
    db_session.add(other_product)
    await db_session.commit()
    in_scope_id = in_scope.id
    inactive_id = inactive.id
    other_id = other_product.id

    denied = await ac.post("/api/v1/notifications/scan-low-stock")
    assert denied.status_code in {401, 403}

    scan = await ac.post("/api/v1/notifications/scan-low-stock", headers=headers)
    assert scan.status_code == 200, scan.text
    body = scan.json()["data"]
    assert body["created"] >= 1
    assert body["low_stock"] == body["created"]

    listed = await ac.get("/api/v1/notifications?group=stock&status=unread", headers=headers)
    assert listed.status_code == 200, listed.text
    rows = [n for n in listed.json()["data"] if n.get("entity_id") == in_scope_id]
    assert len(rows) == 1
    assert rows[0]["category"] == "low_stock"
    assert rows[0].get("group") == "stock"
    assert rows[0]["status"] == "unread"
    assert "N1 Scan Low Stock SKU" in rows[0]["message"]

    notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == tid,
                m.Notification.category == "low_stock",
                m.Notification.entity_id.in_([in_scope_id, inactive_id, other_id]),
            )
        )
    ).scalars().all()
    entity_ids = {n.entity_id for n in notes}
    assert in_scope_id in entity_ids
    assert inactive_id not in entity_ids
    assert other_id not in entity_ids

    again = await ac.post("/api/v1/notifications/scan-low-stock", headers=headers)
    assert again.status_code == 200, again.text
    dupes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == tid,
                m.Notification.category == "low_stock",
                m.Notification.entity_id == in_scope_id,
            )
        )
    ).scalars().all()
    assert len(dupes) == 1
