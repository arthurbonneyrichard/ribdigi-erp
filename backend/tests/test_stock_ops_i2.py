"""Stage 2 I2: stock ops barcode select + adjustment reason codes (BR-5.2)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_adjust_requires_valid_reason_and_persists(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    bad = await ac.post(
        f"/api/v1/inventory/adjust/{seed['p1'].id}",
        headers=headers,
        json={"quantity": -1, "reason": "cycle count"},
    )
    assert bad.status_code == 400
    assert bad.json()["detail"]["code"] == "INVALID_ADJUSTMENT_REASON"

    ok = await ac.post(
        f"/api/v1/inventory/adjust/{seed['p1'].id}",
        headers=headers,
        json={"quantity": -1, "reason": "damage", "notes": "Broken carton"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["reason"] == "damage"

    move = (
        await db_session.execute(
            select(m.StockMovement)
            .where(
                m.StockMovement.tenant_id == seed["t1"].id,
                m.StockMovement.product_id == seed["p1"].id,
                m.StockMovement.movement_type == "adjustment",
            )
            .order_by(m.StockMovement.created_at.desc())
        )
    ).scalars().first()
    assert move is not None
    assert move.reason == "damage"
    assert move.notes == "Broken carton"


@pytest.mark.asyncio
async def test_product_lookup_selects_for_ops(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    seed["p1"].barcode = "4006381333931"
    await db_session.commit()

    r = await ac.get(
        "/api/v1/inventory/products/lookup",
        headers=headers,
        params={"q": "4006381333931", "barcode": "4006381333931"},
    )
    assert r.status_code == 200, r.text
    rows = r.json()["data"]
    assert any((row.get("id") or row.get("product_id")) == seed["p1"].id for row in rows)

    foreign = await ac.get(
        "/api/v1/inventory/products/lookup",
        headers=headers,
        params={"barcode": "no-such-barcode-zzz"},
    )
    assert foreign.status_code == 200
    assert foreign.json()["data"] == []
