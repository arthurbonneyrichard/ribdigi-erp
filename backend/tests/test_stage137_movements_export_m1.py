"""Stage 137 M1 — stock movements CSV export."""

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
async def test_movements_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    product = m.Product(
        tenant_id=seed["t1"].id,
        name="Stage137 Move Product",
        sku="SKU-137-MOVE",
        stock_qty=10,
        selling_price=5,
        cost_price=2,
    )
    db_session.add(product)
    await db_session.flush()

    db_session.add_all(
        [
            m.StockMovement(
                tenant_id=seed["t1"].id,
                product_id=product.id,
                movement_type="stock_in",
                quantity=5,
                quantity_before=5,
                quantity_after=10,
                notes="Stage137 in",
            ),
            m.StockMovement(
                tenant_id=seed["t1"].id,
                product_id=product.id,
                movement_type="stock_out",
                quantity=2,
                quantity_before=10,
                quantity_after=8,
                notes="Stage137 out",
            ),
        ]
    )
    await db_session.commit()

    exported = await ac.get(
        "/api/v1/inventory/movements/export?movement_type=stock_in", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "movement_type" in header and "product_sku" in header
    assert "stock_in" in exported.text
    assert "Stage137 in" in exported.text
    assert "Stage137 out" not in exported.text


def test_movements_export_ui_m1():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "Stage 137" in page
    assert "/inventory/movements/export" in page
    assert "Export movements CSV" in page
