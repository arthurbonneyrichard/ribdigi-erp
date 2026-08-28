"""TaxCalculateRequest.tax_rate_id ∈ UuidIdValue OpenAPI honesty (BR-12.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import TaxCalculateRequest, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_tax_calculate_tax_rate_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = TaxCalculateRequest.model_validate({"amount": 100})
    assert omit.tax_rate_id is None
    ok = TaxCalculateRequest.model_validate(
        {"amount": 100, "tax_rate_id": f"  {_VALID}  "}
    )
    assert ok.tax_rate_id == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "tax_001"):
        with pytest.raises(ValidationError):
            TaxCalculateRequest.model_validate({"amount": 100, "tax_rate_id": bad})


def test_tax_calculate_tax_rate_id_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Tax calculate tax_rate_id OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "tax_rate_id" in docs
    assert "/tax/calculate" in docs


@pytest.mark.asyncio
async def test_tax_calculate_tax_rate_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "tax_001"):
        resp = await ac.post(
            "/api/v1/tax/calculate",
            headers=headers,
            json={"amount": 100, "tax_rate_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        "/api/v1/tax/calculate",
        headers=headers,
        json={"amount": 100, "tax_rate_id": f"  {str(uuid4()).upper()}  "},
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
