"""Stock movement history user attribution (BR-5.3)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_stock_movement_history_includes_user_and_product(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    product = seed["p1"]
    user = seed["super"]
    now = datetime.utcnow()

    store = m.Store(tenant_id=tenant_id, code="MVH-A", name="History Store")
    db_session.add(store)
    await db_session.flush()
    wh = m.Warehouse(
        tenant_id=tenant_id, code="WH-MVH", name="WH History", store_id=store.id
    )
    db_session.add(wh)
    await db_session.flush()

    mv = m.StockMovement(
        tenant_id=tenant_id,
        product_id=product.id,
        warehouse_id=wh.id,
        movement_type="stock_in",
        quantity=7,
        quantity_before=1,
        quantity_after=8,
        reference_type="test_history",
        created_by=user.id,
        created_at=now,
    )
    other = m.StockMovement(
        tenant_id=tenant_id,
        product_id=product.id,
        warehouse_id=wh.id,
        movement_type="stock_out",
        quantity=-1,
        quantity_before=8,
        quantity_after=7,
        reference_type="test_history",
        created_by=None,
        created_at=now - timedelta(minutes=1),
    )
    db_session.add_all([mv, other])
    await db_session.commit()

    report = await ac.get(
        f"/api/v1/reports/inventory/movements?warehouse_id={wh.id}",
        headers=headers,
    )
    assert report.status_code == 200, report.text
    data = report.json()["data"]
    assert data["count"] >= 2
    by_id = {row["id"]: row for row in data["movements"]}
    attributed = by_id[mv.id]
    assert attributed["created_by"] == user.id
    assert attributed["created_by_name"] == user.full_name
    assert attributed["created_by_email"] == user.email
    assert attributed["product_sku"] == product.sku
    assert attributed["product_name"] == product.name
    assert attributed["quantity_before"] == 1
    assert attributed["quantity_after"] == 8

    filtered = await ac.get(
        f"/api/v1/reports/inventory/movements?warehouse_id={wh.id}&created_by={user.id}",
        headers=headers,
    )
    assert filtered.status_code == 200, filtered.text
    fdata = filtered.json()["data"]
    assert fdata["created_by"] == user.id
    assert fdata["count"] >= 1
    assert all(row["created_by"] == user.id for row in fdata["movements"])

    inv = await ac.get(
        f"/api/v1/inventory/movements?warehouse_id={wh.id}&from_date={now.date().isoformat()}",
        headers=headers,
    )
    assert inv.status_code == 200, inv.text
    idata = inv.json()["data"]
    assert isinstance(idata, dict)
    assert "movements" in idata
    assert any(row["id"] == mv.id for row in idata["movements"])
    hit = next(row for row in idata["movements"] if row["id"] == mv.id)
    assert hit["created_by_name"] == user.full_name
    assert hit["product_sku"] == product.sku
