"""GET /inventory|/reports/inventory/movements Query product_id ∈ UuidIdValue (BR-5.3)."""

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
_PATHS = ("/api/v1/inventory/movements", "/api/v1/reports/inventory/movements")


def test_movement_product_id_query_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "prod_001"):
        with pytest.raises(ValidationError):
            _uuid.validate_python(bad)


def test_movement_product_id_query_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Movement selected product only"' in page
    assert "params.set('product_id', productTrim)" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Movement product_id Query OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "product_id" in docs
    assert "UuidIdValue" in docs


@pytest.mark.asyncio
async def test_movement_product_id_query_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    for path in _PATHS:
        for bad in ("", "!!!", "http://evil", "not-a-uuid", "prod_001"):
            resp = await ac.get(f"{path}?product_id={bad}", headers=headers)
            assert resp.status_code == 422, (path, bad, resp.text)

        missing = await ac.get(
            f"{path}?product_id={str(uuid4()).upper()}",
            headers=headers,
        )
        # Unknown product filter still returns list (empty / unfiltered-by-missing)
        # or soft-empty — must not 422 on valid UUID shape.
        assert missing.status_code == 200, missing.text
