"""ProductCategoryUpdate.tax_rate_id ∈ UuidIdValue OpenAPI honesty (BR-5.1 / BR-12.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import ProductCategoryUpdate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_product_category_update_tax_rate_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = ProductCategoryUpdate.model_validate({})
    assert omit.tax_rate_id is None
    ok = ProductCategoryUpdate.model_validate({"tax_rate_id": f"  {_VALID}  "})
    assert ok.tax_rate_id == _VALID.lower()
    nullish = ProductCategoryUpdate.model_validate({"tax_rate_id": None})
    assert nullish.tax_rate_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "tax_001", "a b"):
        with pytest.raises(ValidationError):
            ProductCategoryUpdate.model_validate({"tax_rate_id": bad})


def test_product_category_update_tax_rate_id_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "Edit category tax rate" in page
    assert "tax_rate_id: value" in page
    assert "const value = e.target.value.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Category update tax_rate_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Edit category tax rate" in docs
    assert "PATCH /catalog/categories/{category_id}" in docs


@pytest.mark.asyncio
async def test_product_category_update_tax_rate_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    created = await ac.post(
        "/api/v1/catalog/categories",
        headers=headers,
        json={"code": f"C343{suffix[:4]}".upper(), "name": f"Tip343 Category {suffix}"},
    )
    assert created.status_code == 200, created.text
    cat_id = created.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "tax_001"):
        resp = await ac.patch(
            f"/api/v1/catalog/categories/{cat_id}",
            headers=headers,
            json={"tax_rate_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.patch(
        f"/api/v1/catalog/categories/{cat_id}",
        headers=headers,
        json={"name": f"Tip343 omit tax rate {suffix}"},
    )
    assert omit.status_code == 200, omit.text

    missing = await ac.patch(
        f"/api/v1/catalog/categories/{cat_id}",
        headers=headers,
        json={"tax_rate_id": f"  {str(uuid4()).upper()}  "},
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
