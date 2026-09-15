"""AiDocumentPurchaseInvoiceCreate.purchase_order_id ∈ UuidIdValue OpenAPI honesty."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import AiDocumentPurchaseInvoiceCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_ai_document_purchase_order_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = AiDocumentPurchaseInvoiceCreate.model_validate(
        {"purchase_order_id": f"  {_VALID}  "}
    )
    assert ok.purchase_order_id == _VALID.lower()
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "po_001", "a b", "po"):
        with pytest.raises(ValidationError):
            AiDocumentPurchaseInvoiceCreate.model_validate({"purchase_order_id": bad})
    with pytest.raises(ValidationError):
        AiDocumentPurchaseInvoiceCreate.model_validate({})


def test_ai_document_purchase_order_id_ui_and_docs():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="AI document purchase order"' in page
    assert "purchase_order_id: poId" in page
    assert "draftDocPurchaseOrderId.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "AI document purchase_order_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "AI document purchase order" in docs
    assert "POST /ai/documents/create-purchase-invoice" in docs


@pytest.mark.asyncio
async def test_ai_document_purchase_order_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "po_001", "po"):
        resp = await ac.post(
            "/api/v1/ai/documents/create-purchase-invoice",
            headers=headers,
            json={"purchase_order_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/ai/documents/create-purchase-invoice",
        headers=headers,
        json={},
    )
    assert omit.status_code == 422, omit.text

    missing = await ac.post(
        "/api/v1/ai/documents/create-purchase-invoice",
        headers=headers,
        json={"purchase_order_id": f"  {str(uuid4()).upper()}  "},
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
