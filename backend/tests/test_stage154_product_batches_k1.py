"""Stage 154 K1 — per-product batches CSV export."""

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
async def test_product_batches_export_csv(client):
    ac, seed = client
    headers = await _super(ac, seed)
    product_id = seed["p1"].id
    exported = await ac.get(
        f"/api/v1/products/{product_id}/batches/export",
        headers=headers,
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "batch_number" in header and "quantity" in header and "expiry_date" in header
    assert "product_id" in header


def test_product_batches_export_ui_k1():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "Stage 154" in page
    assert "/batches/export" in page
    assert "Export product batches CSV" in page
