"""ProductCreate / ProductUpdate.category ∈ ProductCategoryLabelValue OpenAPI (BR-5.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import ProductCategoryLabelValue, ProductCreate, ProductUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_label = TypeAdapter(ProductCategoryLabelValue)


def test_product_category_label_value_schema():
    assert _label.validate_python("  Beverages  ") == "Beverages"
    for bad in ("", " ", "!!!", "http://evil", "@@", "a" * 101):
        with pytest.raises(ValidationError):
            _label.validate_python(bad)

    ok = ProductCreate.model_validate({"name": "Widget", "category": "  Snacks  "})
    assert ok.category == "Snacks"
    defaulted = ProductCreate.model_validate({"name": "Widget"})
    assert defaulted.category == "General"
    with pytest.raises(ValidationError):
        ProductCreate.model_validate({"name": "Widget", "category": "!!!"})
    with pytest.raises(ValidationError):
        ProductCreate.model_validate({"name": "Widget", "category": ""})

    patch_ok = ProductUpdate.model_validate({"category": " Dairy "})
    assert patch_ok.category == "Dairy"
    with pytest.raises(ValidationError):
        ProductUpdate.model_validate({"category": "http://x"})


def test_product_category_label_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Product category"' in page
    assert "category_id: productCategoryId || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Product category label OpenAPI" in agents
    assert "ProductCategoryLabelValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "ProductCategoryLabelValue" in docs
    assert "Product category" in docs


@pytest.mark.asyncio
async def test_product_category_label_api_blank_invalid_422(client):
    ac, seed = client
    totp = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=totp
    )
    suffix = uuid4().hex[:8]

    for bad in ("!!!", "", "http://evil.example/p"):
        r = await ac.post(
            "/api/v1/products",
            headers=headers,
            json={"name": f"TIP227 Prod {suffix}", "category": bad},
        )
        assert r.status_code == 422, (bad, r.text)

    hello = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": f"TIP227 Prod OK {suffix}",
            "category": f"  Tip227Cat {suffix}  ",
        },
    )
    assert hello.status_code == 200, hello.text
    assert hello.json()["data"]["category"] == f"Tip227Cat {suffix}"
    product_id = hello.json()["data"]["id"]

    patch_bad = await ac.patch(
        f"/api/v1/products/{product_id}",
        headers=headers,
        json={"category": "!!!"},
    )
    assert patch_bad.status_code == 422, patch_bad.text
