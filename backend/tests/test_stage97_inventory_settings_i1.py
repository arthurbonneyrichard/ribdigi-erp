"""Stage 97 I1 — Inventory & Settings leaf honesty."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
import io

from app import barcode_labels as labels_svc
from app import barcodes as barcode_svc
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_catalog_sub_categories_and_qr_ui():
    inventory = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "Sub Categories" in inventory or "Sub Category" in inventory
    assert "code_type=qr" in inventory or "codeType" in inventory
    assert "Print QR labels" in inventory


def test_settings_aliases_and_anchors_i1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "Tax Rates" in shell
    assert "Email Settings" in shell
    assert "#email" in shell
    assert "SMS Settings" in shell
    assert "#sms" in shell
    assert "Backup & Restore" in shell
    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'id="email"' in company
    assert 'id="sms"' in company


def test_qr_label_render_unit():
    ean = barcode_svc.generate_ean13()
    png = labels_svc.label_png_bytes(
        name="Widget",
        sku="W-1",
        barcode=ean,
        price=12.5,
        currency="GHS",
        code_type="qr",
    )
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    img = Image.open(io.BytesIO(png))
    assert img.size == (400, 220)
    html = labels_svc.build_labels_html(
        [{"name": "W", "sku": "1", "barcode": ean, "price": 1.0, "copies": 1}],
        currency="GHS",
        code_type="qr",
    )
    assert "QR labels" in html
    assert "data:image/png;base64," in html


@pytest.mark.asyncio
async def test_product_qr_label_endpoint(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    gen = await ac.post(
        f"/api/v1/products/{seed['p1'].id}/barcode/generate?format=ean13",
        headers=headers,
    )
    assert gen.status_code == 200, gen.text

    bad = await ac.get(
        f"/api/v1/products/{seed['p1'].id}/labels?format=html&code_type=bogus",
        headers=headers,
    )
    assert bad.status_code == 400

    html = await ac.get(
        f"/api/v1/products/{seed['p1'].id}/labels?format=html&code_type=qr&copies=1",
        headers=headers,
    )
    assert html.status_code == 200, html.text
    assert "QR labels" in html.text or "data:image/png;base64," in html.text

    bulk = await ac.post(
        "/api/v1/inventory/labels",
        headers=headers,
        json={
            "format": "html",
            "code_type": "qr",
            "include_price": False,
            "items": [{"product_id": seed["p1"].id, "copies": 1}],
        },
    )
    assert bulk.status_code == 200, bulk.text
    assert "Print labels" in bulk.text
