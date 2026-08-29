"""Path UuidIdValue OpenAPI honesty for catalog/org/product path ids (#443–#452)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)
_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_path_uuid_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "prod_001"):
        with pytest.raises(ValidationError):
            _uuid.validate_python(bad)


def test_path_uuid_id_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Product path product_id OpenAPI",
        "Catalog path category_id OpenAPI",
        "Catalog path brand_id OpenAPI",
        "Catalog path unit_id OpenAPI",
        "User path user_id OpenAPI",
        "Branch path branch_id OpenAPI",
        "Department path department_id OpenAPI",
        "Warehouse path warehouse_id OpenAPI",
        "Variant path variant_id OpenAPI",
        "Product image path image_id OpenAPI",
    ):
        assert title in agents, title
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Path `product_id` ∈ `UuidIdValue`" in docs
    assert "Path `user_id` ∈ `UuidIdValue`" in docs


@pytest.mark.asyncio
async def test_path_uuid_id_blank_invalid_422(client):
    ac, _seed = client
    # company_admin has users:write for branch/department path checks
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    async def assert_bad(method: str, template: str, **kw):
        for bad in ("not-a-uuid", "!!!", "prod_001"):
            path = template.format(bad=bad)
            resp = await getattr(ac, method)(path, headers=headers, **kw)
            assert resp.status_code == 422, (method, path, resp.text)

        missing = template.format(bad=str(uuid4()))
        resp = await getattr(ac, method)(missing, headers=headers, **kw)
        assert resp.status_code in (200, 400, 404), (method, missing, resp.text)
        assert resp.status_code != 422

    await assert_bad("get", "/api/v1/products/{bad}")
    await assert_bad("get", "/api/v1/products/{bad}/price")
    await assert_bad("get", "/api/v1/users/{bad}")
    await assert_bad("get", "/api/v1/warehouses/{bad}")
    await assert_bad("patch", "/api/v1/catalog/categories/{bad}", json={"name": "X"})
    await assert_bad("patch", "/api/v1/catalog/brands/{bad}", json={"name": "X"})
    await assert_bad("patch", "/api/v1/catalog/units/{bad}", json={"name": "X"})
    await assert_bad("patch", "/api/v1/branches/{bad}", json={"name": "X"})
    await assert_bad("patch", "/api/v1/departments/{bad}", json={"name": "X"})

    # Required Query warehouse_id on warehouse-stock (also UuidIdValue)
    for bad in ("", "!!!", "not-a-uuid", "wh_001"):
        resp = await ac.get(
            f"/api/v1/inventory/warehouse-stock?warehouse_id={bad}",
            headers=headers,
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.get(
        f"/api/v1/inventory/warehouse-stock?warehouse_id={str(uuid4())}",
        headers=headers,
    )
    assert ok.status_code in (200, 400, 404), ok.text
    assert ok.status_code != 422

    pid = str(uuid4())
    for bad in ("not-a-uuid", "var_001", "!!!"):
        resp = await ac.patch(
            f"/api/v1/products/{pid}/variants/{bad}",
            headers=headers,
            json={"selling_price": 1},
        )
        assert resp.status_code == 422, resp.text

        resp = await ac.patch(
            f"/api/v1/products/{pid}/images/{bad}",
            headers=headers,
            json={"is_primary": True},
        )
        assert resp.status_code == 422, resp.text
