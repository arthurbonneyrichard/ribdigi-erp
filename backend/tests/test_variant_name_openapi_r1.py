"""ProductVariantCreate / ProductVariantUpdate.name OpenAPI honesty (BR-5.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import ProductVariantCreate, ProductVariantUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_variant_name_schema():
    ok = ProductVariantCreate.model_validate({"name": "  Large Red  "})
    assert ok.name == "Large Red"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            ProductVariantCreate.model_validate({"name": bad})

    patch_omit = ProductVariantUpdate.model_validate({})
    assert patch_omit.name is None
    patch_ok = ProductVariantUpdate.model_validate({"name": " Renamed Variant "})
    assert patch_ok.name == "Renamed Variant"
    with pytest.raises(ValidationError):
        ProductVariantUpdate.model_validate({"name": "!!!"})
    with pytest.raises(ValidationError):
        ProductVariantUpdate.model_validate({"name": "  "})


def test_variant_name_ui_and_docs():
    inv = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Variant name"' in inv
    assert "variantName.trim()" in inv
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Variant name OpenAPI" in agents
    assert "VariantNameValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "VariantNameValue" in docs
    assert "Variant name" in docs


@pytest.mark.asyncio
async def test_variant_name_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    prod = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={"name": f"Tip133 Parent {suffix}"},
    )
    assert prod.status_code == 200, prod.text
    product_id = prod.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil"):
        r = await ac.post(
            f"/api/v1/products/{product_id}/variants",
            headers=headers,
            json={"name": bad},
        )
        assert r.status_code == 422, (bad, r.text)

    ok = await ac.post(
        f"/api/v1/products/{product_id}/variants",
        headers=headers,
        json={"name": f"  Tip133 Variant {suffix}  "},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["name"] == f"Tip133 Variant {suffix}"
    variant_id = ok.json()["data"]["id"]

    patch_bad = await ac.patch(
        f"/api/v1/products/{product_id}/variants/{variant_id}",
        headers=headers,
        json={"name": "!!!"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    patch_omit = await ac.patch(
        f"/api/v1/products/{product_id}/variants/{variant_id}",
        headers=headers,
        json={},
    )
    assert patch_omit.status_code == 200, patch_omit.text
    assert patch_omit.json()["data"]["name"] == f"Tip133 Variant {suffix}"

    patch_ok = await ac.patch(
        f"/api/v1/products/{product_id}/variants/{variant_id}",
        headers=headers,
        json={"name": f"Renamed {suffix}"},
    )
    assert patch_ok.status_code == 200, patch_ok.text
    assert patch_ok.json()["data"]["name"] == f"Renamed {suffix}"
