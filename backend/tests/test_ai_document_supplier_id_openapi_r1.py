"""AiDocumentPurchaseInvoiceCreate.supplier_id ∈ UuidIdValue OpenAPI honesty."""

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
_PO = "BBBBBBBB-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_ai_document_supplier_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = AiDocumentPurchaseInvoiceCreate.model_validate({"purchase_order_id": _PO})
    assert omit.supplier_id is None
    ok = AiDocumentPurchaseInvoiceCreate.model_validate(
        {"purchase_order_id": _PO, "supplier_id": f"  {_VALID}  "}
    )
    assert ok.supplier_id == _VALID.lower()
    nullish = AiDocumentPurchaseInvoiceCreate.model_validate(
        {"purchase_order_id": _PO, "supplier_id": None}
    )
    assert nullish.supplier_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "sup_001", "a b"):
        with pytest.raises(ValidationError):
            AiDocumentPurchaseInvoiceCreate.model_validate(
                {"purchase_order_id": _PO, "supplier_id": bad}
            )


def test_ai_document_supplier_id_ui_and_docs():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="AI document supplier"' in page
    assert "supplier_id: draftDocSupplierId.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "AI document supplier_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "AI document supplier" in docs
    assert "POST /ai/documents/create-purchase-invoice" in docs


@pytest.mark.asyncio
async def test_ai_document_supplier_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={
            "name": "AI Supplier Tip312",
            "kind": "supplier",
            "email": f"ai-sup-312-{uuid4().hex[:6]}@example.com",
        },
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "notes": "AI supplier tip 312",
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 5}],
        },
    )
    assert po.status_code == 200, po.text
    po_id = po.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "sup_001"):
        resp = await ac.post(
            "/api/v1/ai/documents/create-purchase-invoice",
            headers=headers,
            json={"purchase_order_id": po_id, "supplier_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/ai/documents/create-purchase-invoice",
        headers=headers,
        json={"purchase_order_id": po_id},
    )
    assert omit.status_code == 200, omit.text

    mismatch = await ac.post(
        "/api/v1/ai/documents/create-purchase-invoice",
        headers=headers,
        json={
            "purchase_order_id": po_id,
            "supplier_id": f"  {str(uuid4()).upper()}  ",
        },
    )
    assert mismatch.status_code in (400, 404), mismatch.text
    assert mismatch.status_code != 422
