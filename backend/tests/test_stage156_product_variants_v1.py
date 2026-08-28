"""Stage 156 V1 — path-scoped per-product variants CSV export."""

from __future__ import annotations

from pathlib import Path

import pytest

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_product_variants_path_export_csv(client, db_session):
    """Per-product variants CSV remains for store_manager (company roster dump is denied elsewhere)."""
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id

    variant = m.ProductVariant(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        product_id=product_id,
        name="Stage 156 Variant",
        sku="P1-156-V",
        cost_price=1,
        selling_price=9.5,
        stock_qty=0,
        is_active=True,
    )
    db_session.add(variant)
    await db_session.commit()

    exported = await ac.get(
        f"/api/v1/products/{product_id}/variants/export",
        headers=headers,
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "product_id" in header and "sku" in header and "is_active" in header
    assert "P1-156-V" in text
    assert product_id in text

    missing = await ac.get(
        "/api/v1/products/does-not-exist/variants/export",
        headers=headers,
    )
    assert missing.status_code == 404


def test_product_variants_export_ui_v1():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "Stage 156" in page
    assert "/variants/export" in page
    assert "Export product variants CSV" in page
