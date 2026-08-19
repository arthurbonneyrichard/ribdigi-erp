"""Printable barcode label generation."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app import barcode_labels as labels_svc
from app import barcodes as barcode_svc
from tests.conftest import auth_headers


def test_render_ean13_and_code128_images():
    ean = barcode_svc.generate_ean13()
    ean_img = labels_svc.render_barcode_image(ean)
    assert ean_img.size[0] > 50
    assert ean_img.size[1] > 20

    code = "RDTESTABCD12"
    c128 = labels_svc.render_barcode_image(code)
    assert c128.size[0] > 50

    png = labels_svc.label_png_bytes(
        name="Widget",
        sku="W-1",
        barcode=ean,
        price=12.5,
        currency="GHS",
    )
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    img = Image.open(io.BytesIO(png))
    assert img.size == (400, 220)


def test_labels_html_and_pdf_contain_content():
    ean = barcode_svc.generate_ean13()
    labels = [
        {
            "name": "Alpha Widget",
            "sku": "A-1",
            "barcode": ean,
            "price": 2.0,
            "copies": 2,
        }
    ]
    html = labels_svc.build_labels_html(labels, currency="GHS")
    assert "Print labels" in html
    assert "data:image/png;base64," in html
    assert html.count("class=\"label\"") == 2

    pdf = labels_svc.build_labels_pdf(labels, currency="GHS")
    assert pdf.startswith(b"%PDF")
    assert b"/Im0" in pdf


@pytest.mark.asyncio
async def test_product_label_endpoints(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    # No barcode yet
    missing = await ac.get(f"/api/v1/products/{seed['p1'].id}/labels", headers=headers)
    assert missing.status_code == 400

    gen = await ac.post(
        f"/api/v1/products/{seed['p1'].id}/barcode/generate?format=ean13",
        headers=headers,
    )
    assert gen.status_code == 200, gen.text
    code = gen.json()["data"]["barcode"]

    html = await ac.get(
        f"/api/v1/products/{seed['p1'].id}/labels?format=html&copies=2",
        headers=headers,
    )
    assert html.status_code == 200, html.text
    assert "text/html" in html.headers["content-type"]
    assert code in html.text or "data:image/png;base64," in html.text

    png = await ac.get(
        f"/api/v1/products/{seed['p1'].id}/labels?format=png",
        headers=headers,
    )
    assert png.status_code == 200
    assert png.headers["content-type"] == "image/png"
    assert png.content[:8] == b"\x89PNG\r\n\x1a\n"

    pdf = await ac.get(
        f"/api/v1/products/{seed['p1'].id}/labels?format=pdf",
        headers=headers,
    )
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")

    bulk = await ac.post(
        "/api/v1/inventory/labels",
        headers=headers,
        json={
            "format": "html",
            "include_price": False,
            "items": [{"product_id": seed["p1"].id, "copies": 1}],
        },
    )
    assert bulk.status_code == 200, bulk.text
    assert "Print labels" in bulk.text
