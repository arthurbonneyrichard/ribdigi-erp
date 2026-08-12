"""Stage 118 E1 — catalog CSV export aligned with import template."""

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
async def test_products_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "Export Widget",
            "sku": "EXP-001",
            "cost_price": 1.5,
            "selling_price": 3.0,
            "reorder_level": 2,
        },
    )
    assert created.status_code == 200, created.text

    exported = await ac.get("/api/v1/products/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    assert "name,sku,barcode" in text or "name" in text.splitlines()[0]
    assert "EXP-001" in text
    assert "Export Widget" in text


def test_inventory_page_export_button_e1():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "Stage 118" in page
    assert "/products/export" in page
    assert "Export products CSV" in page
    svc = (ROOT / "backend/app/product_import.py").read_text(encoding="utf-8")
    assert "export_products_csv" in svc
