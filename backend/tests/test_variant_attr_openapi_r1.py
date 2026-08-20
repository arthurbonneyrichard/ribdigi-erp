"""ProductVariantCreate / Update size|color|flavor|dosage ∈ VariantAttrValue OpenAPI (BR-5.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import ProductVariantCreate, ProductVariantUpdate, VariantAttrValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_attr = TypeAdapter(VariantAttrValue)


def test_variant_attr_value_schema():
    assert _attr.validate_python("  100ml  ") == "100ml"
    for bad in ("", " ", "!!!", "http://evil", "@@", "a" * 81):
        with pytest.raises(ValidationError):
            _attr.validate_python(bad)

    ok = ProductVariantCreate.model_validate(
        {
            "name": "Syrup",
            "size": "  100ml  ",
            "color": "amber",
            "flavor": "orange",
            "dosage": "5mg/5ml",
        }
    )
    assert ok.size == "100ml"
    assert ok.color == "amber"
    assert ok.flavor == "orange"
    assert ok.dosage == "5mg/5ml"

    omit = ProductVariantCreate.model_validate({"name": "Plain"})
    assert omit.size is None

    with pytest.raises(ValidationError):
        ProductVariantCreate.model_validate({"name": "X", "size": "!!!"})
    with pytest.raises(ValidationError):
        ProductVariantCreate.model_validate({"name": "X", "color": ""})
    with pytest.raises(ValidationError):
        ProductVariantCreate.model_validate({"name": "X", "flavor": "http://x"})
    with pytest.raises(ValidationError):
        ProductVariantCreate.model_validate({"name": "X", "dosage": "---"})

    patch_omit = ProductVariantUpdate.model_validate({})
    assert patch_omit.size is None
    patch_clear = ProductVariantUpdate.model_validate({"size": None})
    assert patch_clear.size is None
    with pytest.raises(ValidationError):
        ProductVariantUpdate.model_validate({"size": "!!!"})
    with pytest.raises(ValidationError):
        ProductVariantUpdate.model_validate({"color": "  "})


def test_variant_attr_ui_and_docs():
    inv = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Variant size"' in inv
    assert 'aria-label="Variant color"' in inv
    assert 'aria-label="Variant flavor"' in inv
    assert 'aria-label="Variant dosage"' in inv
    assert "variantSize.trim() || null" in inv
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Variant attributes OpenAPI" in agents
    assert "VariantAttrValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "VariantAttrValue" in docs
    assert "Variant size" in docs


@pytest.mark.asyncio
async def test_variant_attr_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    prod = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={"name": f"Tip213 Parent {suffix}"},
    )
    assert prod.status_code == 200, prod.text
    product_id = prod.json()["data"]["id"]

    for field, bad in (
        ("size", "!!!"),
        ("color", ""),
        ("flavor", "http://evil.example/p"),
        ("dosage", "---"),
    ):
        r = await ac.post(
            f"/api/v1/products/{product_id}/variants",
            headers=headers,
            json={"name": f"Bad {field} {suffix}", field: bad},
        )
        assert r.status_code == 422, (field, bad, r.text)

    hello = await ac.post(
        f"/api/v1/products/{product_id}/variants",
        headers=headers,
        json={
            "name": f"VariantAttrValue hello-world {suffix}",
            "size": "  Large  ",
            "color": "Red",
            "flavor": "Mint",
            "dosage": "10mg",
        },
    )
    assert hello.status_code == 200, hello.text
    data = hello.json()["data"]
    assert data["size"] == "Large"
    assert data["color"] == "Red"
    assert data["flavor"] == "Mint"
    assert data["dosage"] == "10mg"
    variant_id = data["id"]

    patch_bad = await ac.patch(
        f"/api/v1/products/{product_id}/variants/{variant_id}",
        headers=headers,
        json={"size": "!!!"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    patch_clear = await ac.patch(
        f"/api/v1/products/{product_id}/variants/{variant_id}",
        headers=headers,
        json={"flavor": None},
    )
    assert patch_clear.status_code == 200, patch_clear.text
    assert patch_clear.json()["data"]["flavor"] is None
    assert patch_clear.json()["data"]["size"] == "Large"

    patch_ok = await ac.patch(
        f"/api/v1/products/{product_id}/variants/{variant_id}",
        headers=headers,
        json={"size": "XL", "dosage": "20mg"},
    )
    assert patch_ok.status_code == 200, patch_ok.text
    assert patch_ok.json()["data"]["size"] == "XL"
    assert patch_ok.json()["data"]["dosage"] == "20mg"
