"""Stage 166 S1 — Hold soft stock reservation via product.reserved_qty."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_pos_hold_soft_reserve_and_release_s1(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    product = seed["p1"]
    product.stock_qty = 20
    product.reserved_qty = 0
    await db_session.commit()

    held = await ac.post(
        "/api/v1/pos/holds",
        headers=headers,
        json={
            "label": "Soft reserve hold",
            "reserve_stock": True,
            "cart_payload": {
                "items": [
                    {
                        "product_id": product.id,
                        "quantity": 3,
                        "discount": 0,
                        "name": product.name,
                        "sku": product.sku,
                        "selling_price": float(product.selling_price or 0),
                    }
                ],
            },
        },
    )
    assert held.status_code == 200, held.text
    data = held.json()["data"]
    assert data["stock_reserved"] is True
    assert data["reservation_lines"]
    hold_id = data["id"]

    await db_session.refresh(product)
    assert float(product.stock_qty or 0) == 20.0
    assert float(product.reserved_qty or 0) == 3.0

    resumed = await ac.post(
        f"/api/v1/pos/holds/{hold_id}/resume", headers=headers, json={}
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["data"]["status"] == "resumed"
    assert resumed.json()["data"]["stock_reserved"] is False

    await db_session.refresh(product)
    assert float(product.reserved_qty or 0) == 0.0


@pytest.mark.asyncio
async def test_pos_hold_default_still_park_only_s1(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    product = seed["p1"]
    product.stock_qty = 15
    product.reserved_qty = 1
    await db_session.commit()
    reserved_before = float(product.reserved_qty or 0)

    held = await ac.post(
        "/api/v1/pos/holds",
        headers=headers,
        json={
            "label": "Park only",
            "cart_payload": {
                "items": [{"product_id": product.id, "quantity": 2}],
            },
        },
    )
    assert held.status_code == 200, held.text
    assert held.json()["data"]["stock_reserved"] is False

    await db_session.refresh(product)
    assert float(product.reserved_qty or 0) == reserved_before


@pytest.mark.asyncio
async def test_pos_hold_reserve_insufficient_stock_s1(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    product = seed["p1"]
    product.stock_qty = 2
    product.reserved_qty = 0
    await db_session.commit()

    held = await ac.post(
        "/api/v1/pos/holds",
        headers=headers,
        json={
            "label": "Too much",
            "reserve_stock": True,
            "cart_payload": {
                "items": [{"product_id": product.id, "quantity": 5}],
            },
        },
    )
    assert held.status_code == 409, held.text


def test_hold_reserve_migration_and_ui_s1():
    mig = (
        ROOT / "backend/alembic/versions/20260813_0094_pos_held_cart_stock_reserve.py"
    ).read_text(encoding="utf-8")
    assert "stock_reserved" in mig
    assert "reservation_lines" in mig
    models = (ROOT / "backend/app/models.py").read_text(encoding="utf-8")
    assert "stock_reserved" in models and "reservation_lines" in models
    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert "reserve_stock" in pos
    holds = (ROOT / "backend/app/pos_holds.py").read_text(encoding="utf-8")
    assert "reserved_qty" in holds
    assert "StockReservation" not in holds or "not SO" in holds.lower() or "soft" in holds.lower()
