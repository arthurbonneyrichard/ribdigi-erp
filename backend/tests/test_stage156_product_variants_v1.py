"""Stage 156 V1 — path-scoped per-product variants CSV export."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_product_variants_path_export_csv(client, db_session):
    """Admins can export per-product variants CSV; store_manager path + roster denied."""
    ac, seed = client
    product_id = seed["p1"].id
    admin_headers = await auth_headers(
        ac,
        email="super@alpha.example.com",
        tenant_slug="alpha",
        totp_code=pyotp.TOTP(seed["super_totp_secret"]).now(),
    )
    mgr_headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

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
        headers=admin_headers,
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
        headers=admin_headers,
    )
    assert missing.status_code == 404

    denied_path = await ac.get(
        f"/api/v1/products/{product_id}/variants/export",
        headers=mgr_headers,
    )
    assert denied_path.status_code == 403, denied_path.text
    assert denied_path.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    denied_roster = await ac.get("/api/v1/products/variants/export", headers=mgr_headers)
    assert denied_roster.status_code == 403, denied_roster.text
    assert denied_roster.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    listed = await ac.get(f"/api/v1/products/{product_id}/variants", headers=mgr_headers)
    assert listed.status_code == 200, listed.text
    assert any(row["sku"] == "P1-156-V" for row in listed.json()["data"])


def test_product_variants_export_ui_v1():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "Stage 156" in page
    assert "/variants/export" in page
    assert "Export product variants CSV" in page
    assert "store_manager path variants CSV dump denied" in page
