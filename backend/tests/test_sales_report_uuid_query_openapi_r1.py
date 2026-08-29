"""Sales report Query UUID filters ∈ UuidIdValue OpenAPI honesty (BR-14.1 / BR-2.5)."""

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
_STORE_PATHS = (
    "/api/v1/reports/sales/daily",
    "/api/v1/reports/sales/monthly",
    "/api/v1/reports/sales/products",
    "/api/v1/reports/sales/customers",
    "/api/v1/reports/sales/returns",
    "/api/v1/reports/sales/salesperson",
)
_DEPT_PATHS = (
    "/api/v1/reports/sales/salesperson",
    "/api/v1/reports/sales/by-store",
    "/api/v1/reports/sales/by-department",
)


def test_sales_report_uuid_query_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "store_001"):
        with pytest.raises(ValidationError):
            _uuid.validate_python(bad)


def test_sales_report_uuid_query_ui_and_docs():
    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Report financial store filter"' in reports
    assert 'aria-label="Report sales category filter"' in reports
    assert 'aria-label="Report department filter"' in reports
    assert "params.set('store_id', storeTrim)" in reports
    assert "category_id: categoryTrim" in reports or "category_id', categoryTrim" in reports
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Sales report store_id Query OpenAPI" in agents
    assert "Sales products category_id Query OpenAPI" in agents
    assert "Sales returns customer_id Query OpenAPI" in agents
    assert "Sales department_id Query OpenAPI" in agents


@pytest.mark.asyncio
async def test_sales_report_store_id_query_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    for path in _STORE_PATHS:
        for bad in ("", "!!!", "http://evil", "not-a-uuid", "store_001"):
            resp = await ac.get(f"{path}?store_id={bad}", headers=headers)
            assert resp.status_code == 422, (path, bad, resp.text)

        missing = await ac.get(
            f"{path}?store_id={str(uuid4()).upper()}",
            headers=headers,
        )
        assert missing.status_code in (200, 400, 404), missing.text
        assert missing.status_code != 422


@pytest.mark.asyncio
async def test_sales_report_category_customer_department_query_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "cat_001"):
        resp = await ac.get(
            f"/api/v1/reports/sales/products?category_id={bad}",
            headers=headers,
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.get(
        f"/api/v1/reports/sales/products?category_id={str(uuid4()).upper()}",
        headers=headers,
    )
    assert ok.status_code in (200, 400, 404), ok.text
    assert ok.status_code != 422

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "cust_001"):
        resp = await ac.get(
            f"/api/v1/reports/sales/returns?customer_id={bad}",
            headers=headers,
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok_cust = await ac.get(
        f"/api/v1/reports/sales/returns?customer_id={str(uuid4()).upper()}",
        headers=headers,
    )
    assert ok_cust.status_code in (200, 400, 404), ok_cust.text
    assert ok_cust.status_code != 422

    for path in _DEPT_PATHS:
        for bad in ("", "!!!", "http://evil", "not-a-uuid", "dept_001"):
            resp = await ac.get(f"{path}?department_id={bad}", headers=headers)
            assert resp.status_code == 422, (path, bad, resp.text)

        missing = await ac.get(
            f"{path}?department_id={str(uuid4()).upper()}",
            headers=headers,
        )
        assert missing.status_code in (200, 400, 404), missing.text
        assert missing.status_code != 422
