"""catalog category code ∈ CategoryCodeValue OpenAPI (BR-5.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import CategoryCodeValue, ProductCategoryCreate, ProductCategoryUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_code = TypeAdapter(CategoryCodeValue)


def test_category_code_value_schema():
    assert _code.validate_python("  bev-01  ") == "bev-01"
    for bad in ("", " ", "!!!", "http://evil", "@@", "a" * 41):
        with pytest.raises(ValidationError):
            _code.validate_python(bad)

    ok = ProductCategoryCreate.model_validate({"code": "  COLA  ", "name": "Colas"})
    assert ok.code == "COLA"
    with pytest.raises(ValidationError):
        ProductCategoryCreate.model_validate({"code": "!!!", "name": "Colas"})
    with pytest.raises(ValidationError):
        ProductCategoryCreate.model_validate({"code": "", "name": "Colas"})

    patch_ok = ProductCategoryUpdate.model_validate({"code": " SODA "})
    assert patch_ok.code == "SODA"
    with pytest.raises(ValidationError):
        ProductCategoryUpdate.model_validate({"code": "http://x"})


def test_category_code_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Category code"' in page
    assert "code: catCode.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Category code OpenAPI" in agents
    assert "CategoryCodeValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "CategoryCodeValue" in docs
    assert "Category code" in docs


@pytest.mark.asyncio
async def test_category_code_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    for bad in ("!!!", "", "http://evil.example/p"):
        r = await ac.post(
            "/api/v1/catalog/categories",
            headers=headers,
            json={"code": bad, "name": f"TIP219 Cat {suffix}"},
        )
        assert r.status_code == 422, (bad, r.text)

    hello = await ac.post(
        "/api/v1/catalog/categories",
        headers=headers,
        json={
            "code": f"  tip219{suffix}  ",
            "name": f"TIP219 Cat OK {suffix}",
        },
    )
    assert hello.status_code == 200, hello.text
    # service uppercases stored code
    assert hello.json()["data"]["code"] == f"tip219{suffix}".upper()
    cat_id = hello.json()["data"]["id"]

    patch_bad = await ac.patch(
        f"/api/v1/catalog/categories/{cat_id}",
        headers=headers,
        json={"code": "!!!"},
    )
    assert patch_bad.status_code == 422, patch_bad.text
