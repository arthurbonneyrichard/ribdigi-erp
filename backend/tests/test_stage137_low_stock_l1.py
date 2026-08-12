"""Stage 137 L1 — low-stock status filter + CSV."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_low_stock_filter_and_export(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    # red: qty <= minimum
    red = m.Product(
        tenant_id=seed["t1"].id,
        name="Stage137 Red",
        sku="SKU-137-RED",
        stock_qty=1,
        minimum_stock=5,
        reorder_level=10,
        selling_price=1,
        cost_price=1,
    )
    # yellow: qty > minimum but <= reorder
    yellow = m.Product(
        tenant_id=seed["t1"].id,
        name="Stage137 Yellow",
        sku="SKU-137-YEL",
        stock_qty=7,
        minimum_stock=5,
        reorder_level=10,
        selling_price=1,
        cost_price=1,
    )
    # green: above reorder — excluded from low-stock list
    green = m.Product(
        tenant_id=seed["t1"].id,
        name="Stage137 Green",
        sku="SKU-137-GRN",
        stock_qty=50,
        minimum_stock=5,
        reorder_level=10,
        selling_price=1,
        cost_price=1,
    )
    db_session.add_all([red, yellow, green])
    await db_session.commit()

    reds = await ac.get(
        "/api/v1/inventory/low-stock?stock_status=red", headers=headers
    )
    assert reds.status_code == 200, reds.text
    rows = reds.json()["data"]
    assert any(r.get("sku") == "SKU-137-RED" for r in rows)
    assert all(r.get("stock_status") == "red" for r in rows)
    assert not any(r.get("sku") == "SKU-137-YEL" for r in rows)
    assert not any(r.get("sku") == "SKU-137-GRN" for r in rows)

    exported = await ac.get(
        "/api/v1/inventory/low-stock/export?stock_status=yellow", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "stock_status" in header and "sku" in header
    assert "SKU-137-YEL" in exported.text
    assert "SKU-137-RED" not in exported.text


def test_low_stock_ui_l1():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "Stage 137" in page
    assert "/inventory/low-stock/export" in page
    assert "Export low-stock CSV" in page
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "stock_status=red" in shell
    assert "Red Low Stock" in shell
    assert "Yellow Low Stock" in shell
