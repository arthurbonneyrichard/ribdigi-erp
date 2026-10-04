"""Inventory expiry report + export (BR-14.2)."""

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
async def test_expiry_report_enrichment_and_warehouse_filter(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    product = seed["p1"]

    wh_a = m.Warehouse(tenant_id=tenant_id, code="WH-EXP-A", name="Expiry A")
    wh_b = m.Warehouse(tenant_id=tenant_id, code="WH-EXP-B", name="Expiry B")
    db_session.add_all([wh_a, wh_b])
    await db_session.flush()

    soon = datetime.utcnow() + timedelta(days=5)
    later = datetime.utcnow() + timedelta(days=90)
    past = datetime.utcnow() - timedelta(days=2)

    db_session.add_all(
        [
            m.ProductBatch(
                tenant_id=tenant_id,
                product_id=product.id,
                warehouse_id=wh_a.id,
                batch_number="EXP-SOON",
                expiry_date=soon,
                quantity=4,
            ),
            m.ProductBatch(
                tenant_id=tenant_id,
                product_id=product.id,
                warehouse_id=wh_b.id,
                batch_number="EXP-OTHER",
                expiry_date=soon,
                quantity=2,
            ),
            m.ProductBatch(
                tenant_id=tenant_id,
                product_id=product.id,
                warehouse_id=wh_a.id,
                batch_number="EXP-FAR",
                expiry_date=later,
                quantity=10,
            ),
            m.ProductBatch(
                tenant_id=tenant_id,
                product_id=product.id,
                warehouse_id=wh_a.id,
                batch_number="EXP-PAST",
                expiry_date=past,
                quantity=1,
            ),
        ]
    )
    await db_session.commit()

    r = await ac.get("/api/v1/reports/inventory/expiry?days=30", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    numbers = {b["batch_number"] for b in data["batches"]}
    assert "EXP-SOON" in numbers
    assert "EXP-OTHER" in numbers
    assert "EXP-PAST" in numbers
    assert "EXP-FAR" not in numbers
    soon_row = next(b for b in data["batches"] if b["batch_number"] == "EXP-SOON")
    assert soon_row["sku"] == product.sku
    assert soon_row["name"] == product.name
    assert soon_row["days_until_expiry"] is not None
    assert data["expired_count"] >= 1

    wh_r = await ac.get(
        f"/api/v1/reports/inventory/expiry?days=30&warehouse_id={wh_a.id}",
        headers=headers,
    )
    assert wh_r.status_code == 200
    wh_data = wh_r.json()["data"]
    assert wh_data["warehouse_id"] == wh_a.id
    assert all(b["warehouse_id"] == wh_a.id for b in wh_data["batches"])
    assert "EXP-OTHER" not in {b["batch_number"] for b in wh_data["batches"]}

    bad = await ac.get(
        "/api/v1/reports/inventory/expiry?warehouse_id=00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert bad.status_code == 404


def test_flatten_expiry_export():
    from app.report_export import EXPORTABLE, flatten_report

    assert "inventory_expiry" in EXPORTABLE
    rows, lines, title = flatten_report(
        "inventory_expiry",
        {
            "count": 1,
            "batches": [
                {
                    "sku": "SKU-1",
                    "batch_number": "B-9",
                    "expiry_date": "2026-09-01",
                    "days_until_expiry": 10,
                    "quantity": 3,
                }
            ],
        },
    )
    assert title == "Inventory Expiry"
    assert rows[0]["batch_number"] == "B-9"
    assert any("B-9" in line for line in lines)
