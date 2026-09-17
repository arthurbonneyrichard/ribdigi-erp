"""ProductCreate / ProductUpdate.description OpenAPI honesty (BR-5.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import ProductCreate, ProductUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_product_description_schema():
    omit = ProductCreate.model_validate({"name": "Widget"})
    assert omit.description is None
    nullish = ProductCreate.model_validate({"name": "Widget", "description": None})
    assert nullish.description is None
    ok = ProductCreate.model_validate(
        {"name": "Widget", "description": "  Soft cotton tee  "}
    )
    assert ok.description == "Soft cotton tee"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            ProductCreate.model_validate({"name": "Widget", "description": bad})

    patch_omit = ProductUpdate.model_validate({})
    assert patch_omit.description is None
    patch_ok = ProductUpdate.model_validate({"description": " Renamed copy "})
    assert patch_ok.description == "Renamed copy"
    with pytest.raises(ValidationError):
        ProductUpdate.model_validate({"description": "!!!"})
    with pytest.raises(ValidationError):
        ProductUpdate.model_validate({"description": "  "})


def test_product_description_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Product description"' in page
    assert 'aria-label="Edit product description"' in page
    assert "productDescription.trim() || null" in page
    assert "editDescription.trim() || null" in page
    assert 'aria-label="Save product"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Product description OpenAPI" in agents
    assert "ProductDescriptionValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "ProductDescriptionValue" in docs
    assert "Product description" in docs


@pytest.mark.asyncio
async def test_product_description_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/products",
            headers=admin,
            json={"name": f"Tip155 Bad {suffix}", "description": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/products",
        headers=admin,
        json={"name": f"Tip155 Omit {suffix}"},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"].get("description") in (None, "")

    ok = await ac.post(
        "/api/v1/products",
        headers=admin,
        json={
            "name": f"Tip155 Ok {suffix}",
            "description": f"  Tip155 narrative {suffix}  ",
        },
    )
    assert ok.status_code == 200, ok.text
    pid = ok.json()["data"]["id"]
    assert ok.json()["data"]["description"] == f"Tip155 narrative {suffix}"

    for bad in ("", "!!!", "http://evil"):
        bad_patch = await ac.patch(
            f"/api/v1/products/{pid}",
            headers=admin,
            json={"description": bad},
        )
        assert bad_patch.status_code == 422, (bad, bad_patch.text)

    renamed = await ac.patch(
        f"/api/v1/products/{pid}",
        headers=admin,
        json={"description": f"  Tip155 renamed {suffix}  "},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["description"] == f"Tip155 renamed {suffix}"
