"""SalesReturnCreate.sales_invoice_id ∈ UuidIdValue OpenAPI honesty (BR-7.5)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import SalesReturnCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
_ITEMS = [
    {
        "product_id": "11111111-2222-3333-4444-555555555555",
        "quantity": 1,
        "condition": "sellable",
    }
]


def test_sr_sales_invoice_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = SalesReturnCreate.model_validate(
        {
            "sales_invoice_id": f"  {_VALID}  ",
            "reason": "damaged",
            "items": _ITEMS,
        }
    )
    assert ok.sales_invoice_id == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "inv_001"):
        with pytest.raises(ValidationError):
            SalesReturnCreate.model_validate(
                {"sales_invoice_id": bad, "reason": "damaged", "items": _ITEMS}
            )
    with pytest.raises(ValidationError):
        SalesReturnCreate.model_validate({"reason": "damaged", "items": _ITEMS})


def test_sr_sales_invoice_id_ui_and_docs():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Return from invoice"' in page
    assert "sales_invoice_id: invoiceId.trim()" in page
    assert 'aria-label="Create sales return"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Sales return sales_invoice_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "UuidIdValue" in docs
    assert "POST /sales/returns" in docs
    assert "Return from invoice" in docs


@pytest.mark.asyncio
async def test_sr_sales_invoice_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    item = {
        "product_id": seed["p1"].id,
        "quantity": 1,
        "condition": "sellable",
    }

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "inv_001"):
        resp = await ac.post(
            "/api/v1/sales/returns",
            headers=headers,
            json={"sales_invoice_id": bad, "reason": "damaged", "items": [item]},
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        "/api/v1/sales/returns",
        headers=headers,
        json={
            "sales_invoice_id": f"  {str(uuid4()).upper()}  ",
            "reason": "damaged",
            "items": [item],
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
