"""Purchases report Query warehouse_id / store_id / supplier_id ∈ UuidIdValue (BR-14.3)."""

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
_LOCATION_PATHS = (
    "/api/v1/reports/purchases/summary",
    "/api/v1/reports/purchases/suppliers",
    "/api/v1/reports/purchases/pending-orders",
    "/api/v1/reports/purchases/returns",
)
_SUPPLIER_PATHS = (
    "/api/v1/reports/purchases/suppliers",
    "/api/v1/reports/purchases/pending-orders",
    "/api/v1/reports/purchases/returns",
)


def test_purchases_report_uuid_query_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid"):
        with pytest.raises(ValidationError):
            _uuid.validate_python(bad)


def test_purchases_report_uuid_query_ui_and_docs():
    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Report purchases store filter"' in reports
    assert 'aria-label="Report purchases warehouse filter"' in reports
    assert "params.set('warehouse_id', warehouseTrim)" in reports
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Purchases report location Query OpenAPI" in agents
    assert "Purchases report supplier_id Query OpenAPI" in agents


@pytest.mark.asyncio
async def test_purchases_report_location_supplier_query_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    for path in _LOCATION_PATHS:
        for key, token in (("store_id", "store_001"), ("warehouse_id", "wh_001")):
            for bad in ("", "!!!", "http://evil", "not-a-uuid", token):
                resp = await ac.get(f"{path}?{key}={bad}", headers=headers)
                assert resp.status_code == 422, (path, key, bad, resp.text)

            missing = await ac.get(
                f"{path}?{key}={str(uuid4()).upper()}",
                headers=headers,
            )
            assert missing.status_code in (200, 400, 404), missing.text
            assert missing.status_code != 422

    for path in _SUPPLIER_PATHS:
        for bad in ("", "!!!", "http://evil", "not-a-uuid", "sup_001"):
            resp = await ac.get(f"{path}?supplier_id={bad}", headers=headers)
            assert resp.status_code == 422, (path, bad, resp.text)

        missing = await ac.get(
            f"{path}?supplier_id={str(uuid4()).upper()}",
            headers=headers,
        )
        assert missing.status_code in (200, 400, 404), missing.text
        assert missing.status_code != 422
