"""ProductCreate / Update + variant barcode OpenAPI honesty (BR-5.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import (
    ProductCreate,
    ProductUpdate,
    ProductVariantCreate,
    ProductVariantUpdate,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_product_barcode_schema():
    omit = ProductCreate.model_validate({"name": "Widget"})
    assert omit.barcode is None
    ok = ProductCreate.model_validate({"name": "Widget", "barcode": "  sku-2026  "})
    assert ok.barcode == "SKU-2026"
    for bad in ("", " ", "!!!", "!!!!", "http://evil", "ab", "@@"):
        with pytest.raises(ValidationError):
            ProductCreate.model_validate({"name": "Widget", "barcode": bad})

    patch_omit = ProductUpdate.model_validate({})
    assert patch_omit.barcode is None
    patch_ok = ProductUpdate.model_validate({"barcode": "  BC-1001  "})
    assert patch_ok.barcode == "BC-1001"
    with pytest.raises(ValidationError):
        ProductUpdate.model_validate({"barcode": "!!!!"})
    with pytest.raises(ValidationError):
        ProductUpdate.model_validate({"barcode": "  "})

    var_ok = ProductVariantCreate.model_validate({"name": "Large", "barcode": "VAR-0001"})
    assert var_ok.barcode == "VAR-0001"
    with pytest.raises(ValidationError):
        ProductVariantCreate.model_validate({"name": "Large", "barcode": "ab"})
    with pytest.raises(ValidationError):
        ProductVariantUpdate.model_validate({"barcode": ""})


def test_product_barcode_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Product barcode"' in page
    assert 'aria-label="Edit product barcode"' in page
    assert 'aria-label="Variant barcode"' in page
    assert "productBarcode.trim() || null" in page
    assert "editBarcode.trim() || null" in page
    assert "variantBarcode.trim() || null" in page
    assert 'aria-label="Save product"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Product barcode OpenAPI" in agents
    assert "ProductBarcodeValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "ProductBarcodeValue" in docs
    assert "Product barcode" in docs


@pytest.mark.asyncio
async def test_product_barcode_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    for bad in ("", "!!!!", "http://evil", "ab"):
        resp = await ac.post(
            "/api/v1/products",
            headers=admin,
            json={"name": f"Tip154 Bad {suffix}", "barcode": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/products",
        headers=admin,
        json={"name": f"Tip154 Omit {suffix}"},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"].get("barcode") in (None, "")

    ok = await ac.post(
        "/api/v1/products",
        headers=admin,
        json={
            "name": f"Tip154 Ok {suffix}",
            "barcode": f"  tip154-{suffix[:6]}  ",
        },
    )
    assert ok.status_code == 200, ok.text
    pid = ok.json()["data"]["id"]
    assert ok.json()["data"]["barcode"] == f"TIP154-{suffix[:6]}".upper()

    for bad in ("", "!!!!", "ab"):
        bad_patch = await ac.patch(
            f"/api/v1/products/{pid}",
            headers=admin,
            json={"barcode": bad},
        )
        assert bad_patch.status_code == 422, (bad, bad_patch.text)

    renamed = await ac.patch(
        f"/api/v1/products/{pid}",
        headers=admin,
        json={"barcode": f"  tip154b-{suffix[:5]}  "},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["barcode"] == f"TIP154B-{suffix[:5]}".upper()
