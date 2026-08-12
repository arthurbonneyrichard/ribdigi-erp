"""Stage 156 G1 — per-product images metadata CSV export."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def _png_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"fake-png-bytes-stage156"


@pytest.mark.asyncio
async def test_product_images_export_csv(client, tmp_path, monkeypatch):
    from app import storage as storage_svc

    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    monkeypatch.setattr(storage_svc.settings, "STORAGE_BACKEND", "local")
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id

    uploaded = await ac.post(
        f"/api/v1/products/{product_id}/images",
        headers=headers,
        files={"file": ("stage156.png", _png_bytes(), "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text

    exported = await ac.get(
        f"/api/v1/products/{product_id}/images/export",
        headers=headers,
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "storage_key" in header and "is_primary" in header and "original_filename" in header
    assert "product_id" in header
    assert product_id in text
    assert "stage156.png" in text or "image/png" in text


def test_product_images_export_ui_g1():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "Stage 156" in page
    assert "/images/export" in page
    assert "Export images CSV" in page
