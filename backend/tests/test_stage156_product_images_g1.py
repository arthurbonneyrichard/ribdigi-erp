"""Stage 156 G1 — per-product images metadata CSV export."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_product_images_export_csv(client, db_session):
    """Admins can export product images CSV; store_manager is denied (list remains)."""
    ac, seed = client
    product_id = seed["p1"].id
    admin_headers = await auth_headers(
        ac,
        email="super@alpha.example.com",
        tenant_slug="alpha",
        totp_code=pyotp.TOTP(seed["super_totp_secret"]).now(),
    )
    mgr_headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    image = m.ProductImage(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        product_id=product_id,
        storage_key="products/stage156.png",
        content_type="image/png",
        original_filename="stage156.png",
        sort_order=0,
        is_primary=True,
    )
    db_session.add(image)
    await db_session.commit()

    exported = await ac.get(
        f"/api/v1/products/{product_id}/images/export",
        headers=admin_headers,
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "storage_key" in header and "is_primary" in header and "original_filename" in header
    assert "product_id" in header
    assert product_id in text
    assert "stage156.png" in text or "image/png" in text

    denied = await ac.get(
        f"/api/v1/products/{product_id}/images/export",
        headers=mgr_headers,
    )
    assert denied.status_code == 403, denied.text
    assert denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    listed = await ac.get(f"/api/v1/products/{product_id}/images", headers=mgr_headers)
    assert listed.status_code == 200, listed.text
    assert any(row["id"] == image.id for row in listed.json()["data"])


def test_product_images_export_ui_g1():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "Stage 156" in page
    assert "/images/export" in page
    assert "Export images CSV" in page
