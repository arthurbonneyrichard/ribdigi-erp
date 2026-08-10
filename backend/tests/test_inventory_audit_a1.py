"""Stage 17 A1: inventory domain audit for product/stock mutations (BR-17.1)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app.catalog_meta import product_audit_diff, product_audit_snapshot
from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_product_create_update_deactivate_audit_with_before_after(client, db_session):
    """BR-17.1 Product Changes: create / update / soft-delete with before/after + hash."""
    ac, seed = client
    headers = await _mgr(ac)
    super_h = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "S17 A1 Audit SKU",
            "sku": "S17-A1-AUD",
            "cost_price": 3,
            "selling_price": 7,
            "reorder_level": 10,
            "minimum_stock": 2,
            "stock_qty": 0,
        },
    )
    assert created.status_code == 200, created.text
    product_id = created.json()["data"]["id"]

    create_logs = await ac.get(
        "/api/v1/audit-logs",
        headers=super_h,
        params={"action": "product_create", "module": "inventory"},
    )
    assert create_logs.status_code == 200, create_logs.text
    crow = next(r for r in create_logs.json()["data"] if r["entity_id"] == product_id)
    assert crow["integrity_hash"]
    assert crow["module"] == "inventory"
    assert crow["entity"] == "product"
    assert crow["details"]["sku"] == "S17-A1-AUD"
    assert crow["details"]["after"]["name"] == "S17 A1 Audit SKU"
    assert float(crow["details"]["after"]["selling_price"]) == pytest.approx(7)

    patched = await ac.patch(
        f"/api/v1/products/{product_id}",
        headers=headers,
        json={"name": "S17 A1 Renamed", "selling_price": 9.5, "reorder_level": 15},
    )
    assert patched.status_code == 200, patched.text

    update_logs = await ac.get(
        "/api/v1/audit-logs",
        headers=super_h,
        params={"action": "product_update", "module": "inventory"},
    )
    assert update_logs.status_code == 200, update_logs.text
    urow = next(r for r in update_logs.json()["data"] if r["entity_id"] == product_id)
    assert urow["integrity_hash"]
    assert "name" in urow["details"]["fields"]
    assert urow["details"]["before"]["name"] == "S17 A1 Audit SKU"
    assert urow["details"]["after"]["name"] == "S17 A1 Renamed"
    assert float(urow["details"]["before"]["selling_price"]) == pytest.approx(7)
    assert float(urow["details"]["after"]["selling_price"]) == pytest.approx(9.5)
    assert float(urow["details"]["before"]["reorder_level"]) == pytest.approx(10)
    assert float(urow["details"]["after"]["reorder_level"]) == pytest.approx(15)

    deactivated = await ac.patch(
        f"/api/v1/products/{product_id}",
        headers=headers,
        json={"is_active": False},
    )
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["data"]["is_active"] is False

    deact_logs = await ac.get(
        "/api/v1/audit-logs",
        headers=super_h,
        params={"action": "product_deactivate", "module": "inventory"},
    )
    assert deact_logs.status_code == 200, deact_logs.text
    drow = next(r for r in deact_logs.json()["data"] if r["entity_id"] == product_id)
    assert drow["integrity_hash"]
    assert drow["details"]["before"]["is_active"] is True
    assert drow["details"]["after"]["is_active"] is False

    verify = await ac.get("/api/v1/audit-logs/verify", headers=super_h)
    assert verify.status_code == 200
    assert verify.json()["data"]["valid"] is True


@pytest.mark.asyncio
async def test_stock_mutations_emit_inventory_audit(client, db_session):
    """Stock-in / adjust domain audits include before/after qty (apply_stock_change)."""
    ac, seed = client
    headers = await _mgr(ac)
    super_h = await _super(ac, seed)
    tenant_id = seed["t1"].id

    product = m.Product(
        tenant_id=tenant_id,
        name="S17 A1 Stock Audit",
        sku="S17-A1-STK",
        cost_price=1,
        selling_price=2,
        stock_qty=0,
    )
    wh = m.Warehouse(tenant_id=tenant_id, name="S17 A1 WH", code="S17A1WH")
    db_session.add_all([product, wh])
    await db_session.commit()
    product_id, wh_id = product.id, wh.id

    stock_in = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={
            "product_id": product_id,
            "quantity": 12,
            "warehouse_id": wh_id,
            "notes": "S17 A1 stock-in",
        },
    )
    assert stock_in.status_code == 200, stock_in.text

    in_logs = await ac.get(
        "/api/v1/audit-logs",
        headers=super_h,
        params={"action": "stock_stock_in", "module": "inventory"},
    )
    assert in_logs.status_code == 200, in_logs.text
    irow = next(r for r in in_logs.json()["data"] if r["entity_id"] == product_id)
    assert irow["integrity_hash"]
    assert float(irow["details"]["quantity_delta"]) == pytest.approx(12)
    assert float(irow["details"]["before"]) == pytest.approx(0)
    assert float(irow["details"]["after"]) == pytest.approx(12)
    assert irow["details"]["warehouse_id"] == wh_id

    adjust = await ac.post(
        f"/api/v1/inventory/adjust/{product_id}",
        headers=headers,
        json={
            "quantity": -2,
            "reason": "damage",
            "warehouse_id": wh_id,
            "notes": "S17 A1 damage",
        },
    )
    assert adjust.status_code == 200, adjust.text

    adj_logs = await ac.get(
        "/api/v1/audit-logs",
        headers=super_h,
        params={"action": "stock_adjustment", "module": "inventory"},
    )
    assert adj_logs.status_code == 200, adj_logs.text
    arow = next(
        r
        for r in adj_logs.json()["data"]
        if r["entity_id"] == product_id and float(r["details"].get("quantity_delta") or 0) == -2
    )
    assert arow["integrity_hash"]
    assert float(arow["details"]["before"]) == pytest.approx(12)
    assert float(arow["details"]["after"]) == pytest.approx(10)
    assert arow["details"]["reason"] == "damage"


def test_product_audit_snapshot_helpers():
    row = m.Product(
        id="p-aud",
        tenant_id="t1",
        name="Snap",
        sku="SNAP-1",
        cost_price=1,
        selling_price=2,
        stock_qty=5,
        minimum_stock=1,
        reorder_level=3,
        is_active=True,
    )
    snap = product_audit_snapshot(row)
    assert snap["sku"] == "SNAP-1"
    assert snap["name"] == "Snap"
    assert "stock_qty" not in snap  # stock qty changes use stock_* actions
    before = {**snap, "name": "Old", "selling_price": 2.0}
    after = {**snap, "name": "New", "selling_price": 4.0}
    b, a = product_audit_diff(before, after)
    assert b == {"name": "Old", "selling_price": 2.0}
    assert a == {"name": "New", "selling_price": 4.0}


def test_inventory_audit_a1_docs():
    plan = (ROOT / "docs/STAGE_17_PLAN.md").read_text(encoding="utf-8")
    assert "| **A1**" in plan
    assert "test_inventory_audit_a1.py" in plan
    assert "COMPLETE" in plan
    br = (ROOT / "docs/BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    assert "Stage 17 A1" in br
    assert "[x] **Product Changes:**" in br
    sec = (ROOT / "docs/SECURITY_GUIDE.md").read_text(encoding="utf-8")
    assert "product_create" in sec
    assert "product_deactivate" in sec
