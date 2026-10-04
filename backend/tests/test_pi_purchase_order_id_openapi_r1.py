"""PurchaseInvoiceCreate.purchase_order_id ∈ UuidIdValue OpenAPI honesty (BR-6.5)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import PurchaseInvoiceCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_pi_purchase_order_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = PurchaseInvoiceCreate.model_validate({})
    assert omit.purchase_order_id is None
    ok = PurchaseInvoiceCreate.model_validate(
        {"purchase_order_id": f"  {_VALID}  "}
    )
    assert ok.purchase_order_id == _VALID.lower()
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "po_001"):
        with pytest.raises(ValidationError):
            PurchaseInvoiceCreate.model_validate({"purchase_order_id": bad})


def test_pi_purchase_order_id_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Purchase invoice purchase_order_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "purchase_order_id" in docs
    assert "POST /purchasing/invoices" in docs


@pytest.mark.asyncio
async def test_pi_purchase_order_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "po_001"):
        resp = await ac.post(
            "/api/v1/purchasing/invoices",
            headers=headers,
            json={"purchase_order_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={"purchase_order_id": f"  {str(uuid4()).upper()}  "},
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
