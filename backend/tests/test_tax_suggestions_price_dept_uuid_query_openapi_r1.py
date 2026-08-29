"""Tax / suggestions / product-price / departments Query UuidIdValue OpenAPI honesty."""

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


def test_misc_uuid_query_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid"):
        with pytest.raises(ValidationError):
            _uuid.validate_python(bad)


def test_misc_uuid_query_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Tax report store_id Query OpenAPI" in agents
    assert "Purchasing suggestions location Query OpenAPI" in agents
    assert "Product price Query OpenAPI" in agents
    assert "Departments list branch_id Query OpenAPI" in agents
    tax = (ROOT / "frontend/app/tax/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Tax report store filter"' in tax
    assert "storeTrim" in tax and "store_id" in tax
    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert "/purchasing/suggestions/low-stock${qs()}" in reports
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "customerTrim" in sales and "variantTrim" in sales
    assert 'aria-label="Sale customer"' in sales
    assert 'aria-label="Sales variant"' in sales


@pytest.mark.asyncio
async def test_tax_report_store_id_query_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    for path in ("/api/v1/reports/tax", "/api/v1/reports/tax/filing"):
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
async def test_suggestions_location_query_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    path = "/api/v1/purchasing/suggestions/low-stock"
    for key, token in (("store_id", "store_001"), ("warehouse_id", "wh_001")):
        for bad in ("", "!!!", "http://evil", "not-a-uuid", token):
            resp = await ac.get(f"{path}?{key}={bad}", headers=headers)
            assert resp.status_code == 422, (key, bad, resp.text)

        missing = await ac.get(
            f"{path}?{key}={str(uuid4()).upper()}",
            headers=headers,
        )
        assert missing.status_code in (200, 400, 404), missing.text
        assert missing.status_code != 422


@pytest.mark.asyncio
async def test_product_price_and_departments_query_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    product_id = str(uuid4())
    for key, token in (("customer_id", "cust_001"), ("variant_id", "var_001")):
        for bad in ("", "!!!", "http://evil", "not-a-uuid", token):
            resp = await ac.get(
                f"/api/v1/products/{product_id}/price?{key}={bad}",
                headers=headers,
            )
            # Path product may 404 before Query when product missing; blank/invalid Query must 422.
            assert resp.status_code == 422, (key, bad, resp.text)

        shaped = await ac.get(
            f"/api/v1/products/{product_id}/price?{key}={str(uuid4()).upper()}",
            headers=headers,
        )
        assert shaped.status_code in (200, 400, 404), shaped.text
        assert shaped.status_code != 422

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "branch_001"):
        resp = await ac.get(f"/api/v1/departments?branch_id={bad}", headers=headers)
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.get(
        f"/api/v1/departments?branch_id={str(uuid4()).upper()}",
        headers=headers,
    )
    assert ok.status_code in (200, 400, 404), ok.text
    assert ok.status_code != 422
