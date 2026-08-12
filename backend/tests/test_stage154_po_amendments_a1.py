"""Stage 154 A1 — purchase order amendments CSV export."""

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
async def test_po_amendments_export_csv(client):
    ac, seed = client
    headers = await _super(ac, seed)
    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "Stage 154 Supplier", "code": "SUP-154"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]
    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 2, "unit_cost": 5}],
        },
    )
    assert po.status_code == 200, po.text
    po_id = po.json()["data"]["id"]
    exported = await ac.get(
        f"/api/v1/purchasing/orders/{po_id}/amendments/export",
        headers=headers,
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "revision" in header and "reason" in header and "po_number" in header


def test_po_amendments_export_ui_a1():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "Stage 154" in page
    assert "/amendments/export" in page
    assert "Export amendments CSV" in page
