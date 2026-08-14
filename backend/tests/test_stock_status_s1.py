"""Product list stock traffic lights (BR-5.5)."""

from __future__ import annotations

import pyotp
import pytest

from app.catalog_meta import compute_stock_status
from tests.conftest import auth_headers


@pytest.mark.parametrize(
    "qty,reorder,expected",
    [
        (0, 0, "red"),
        (0, 10, "red"),
        (5, 10, "red"),
        (10, 10, "red"),
        (11, 10, "yellow"),
        (15, 10, "yellow"),
        (15.1, 10, "green"),
        (100, 0, "green"),
        (1, 0, "green"),
    ],
)
def test_compute_stock_status_bands(qty, reorder, expected):
    assert compute_stock_status(qty, reorder)["status"] == expected


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_product_serialize_exposes_stock_status(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)

    yellow = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "Near Reorder Widget",
            "sku": "TL-S1-YEL",
            "selling_price": 9.99,
            "cost_price": 4.0,
            "stock_qty": 12,
            "reorder_level": 10,
        },
    )
    assert yellow.status_code == 200, yellow.text
    y = yellow.json()["data"]
    assert y["stock_qty"] == pytest.approx(12.0)
    assert y["stock_status"] == "yellow"
    assert y["stock_status_label"] == "near_reorder"

    red = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "Low Stock Widget",
            "sku": "TL-S1-RED",
            "selling_price": 9.99,
            "cost_price": 4.0,
            "stock_qty": 5,
            "reorder_level": 10,
        },
    )
    assert red.status_code == 200, red.text
    r = red.json()["data"]
    assert r["stock_status"] == "red"
    assert r["stock_status_label"] == "low"

    green = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "Healthy Stock Widget",
            "sku": "TL-S1-GRN",
            "selling_price": 9.99,
            "cost_price": 4.0,
            "stock_qty": 50,
            "reorder_level": 10,
        },
    )
    assert green.status_code == 200, green.text
    g = green.json()["data"]
    assert g["stock_status"] == "green"
    assert g["stock_status_label"] == "ok"

    listed = await ac.get("/api/v1/products", headers=headers)
    assert listed.status_code == 200
    by_id = {p["id"]: p for p in listed.json()["data"]}
    assert by_id[y["id"]]["stock_status"] == "yellow"
    assert by_id[r["id"]]["stock_status"] == "red"
    assert by_id[g["id"]]["stock_status"] == "green"
