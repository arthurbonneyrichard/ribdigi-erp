"""ProductCategoryCreate.parent_id ∈ UuidIdValue OpenAPI honesty (BR-5.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import ProductCategoryCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_product_category_create_parent_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = ProductCategoryCreate.model_validate({"code": "BEV", "name": "Beverages"})
    assert omit.parent_id is None
    ok = ProductCategoryCreate.model_validate(
        {"code": "BEV", "name": "Beverages", "parent_id": f"  {_VALID}  "}
    )
    assert ok.parent_id == _VALID.lower()
    nullish = ProductCategoryCreate.model_validate(
        {"code": "BEV", "name": "Beverages", "parent_id": None}
    )
    assert nullish.parent_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "cat_001", "a b"):
        with pytest.raises(ValidationError):
            ProductCategoryCreate.model_validate(
                {"code": "BEV", "name": "Beverages", "parent_id": bad}
            )


def test_product_category_create_parent_id_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Category parent"' in page
    assert "parent_id: catParentId.trim() || null" in page
    assert 'aria-label="Add category"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Category create parent_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Category parent" in docs
    assert "POST /catalog/categories" in docs


@pytest.mark.asyncio
async def test_product_category_create_parent_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "cat_001"):
        resp = await ac.post(
            "/api/v1/catalog/categories",
            headers=headers,
            json={
                "code": f"C340{suffix[:4]}".upper(),
                "name": f"Tip340 Category {suffix}",
                "parent_id": bad,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/catalog/categories",
        headers=headers,
        json={
            "code": f"C340O{suffix[:3]}".upper(),
            "name": f"Tip340 omit parent {suffix}",
        },
    )
    assert omit.status_code == 200, omit.text

    missing = await ac.post(
        "/api/v1/catalog/categories",
        headers=headers,
        json={
            "code": f"C340M{suffix[:3]}".upper(),
            "name": f"Tip340 missing parent {suffix}",
            "parent_id": f"  {str(uuid4()).upper()}  ",
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
