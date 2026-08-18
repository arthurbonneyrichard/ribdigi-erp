"""AI document draft expense_date / invoice_date OpenAPI honesty (BR-21.8)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import (
    AiDocumentExpenseCreate,
    AiDocumentPurchaseInvoiceCreate,
    IsoDateQueryValue,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_iso_date_query_schema_for_ai_document_draft_dates():
    adapter = TypeAdapter(IsoDateQueryValue)
    assert adapter.validate_python(" 2026-08-01 ") == "2026-08-01"
    for bad in ("", " ", "not-a-date", "01/02/2024", "2026-13-01"):
        with pytest.raises(ValidationError):
            adapter.validate_python(bad)


def test_ai_document_draft_date_schema_rejects_invalid():
    with pytest.raises(ValidationError):
        AiDocumentExpenseCreate.model_validate({"amount": 1, "expense_date": "not-a-date"})
    with pytest.raises(ValidationError):
        AiDocumentExpenseCreate.model_validate({"amount": 1, "expense_date": ""})
    with pytest.raises(ValidationError):
        AiDocumentExpenseCreate.model_validate({"amount": 1, "expense_date": "01/02/2024"})
    with pytest.raises(ValidationError):
        AiDocumentExpenseCreate.model_validate({"amount": 1, "unknown_key": True})

    ok = AiDocumentExpenseCreate.model_validate(
        {"amount": 12.5, "expense_date": " 2026-08-01 "}
    )
    assert ok.expense_date == "2026-08-01"
    omit = AiDocumentExpenseCreate.model_validate({"amount": 12.5})
    assert omit.expense_date is None

    with pytest.raises(ValidationError):
        AiDocumentPurchaseInvoiceCreate.model_validate(
            {"purchase_order_id": "po", "invoice_date": "not-a-date"}
        )
    with pytest.raises(ValidationError):
        AiDocumentPurchaseInvoiceCreate.model_validate(
            {"purchase_order_id": "po", "invoice_date": ""}
        )
    with pytest.raises(ValidationError):
        AiDocumentPurchaseInvoiceCreate.model_validate(
            {"purchase_order_id": "po", "extra": 1}
        )

    pi = AiDocumentPurchaseInvoiceCreate.model_validate(
        {"purchase_order_id": "po", "invoice_date": " 2026-08-10 "}
    )
    assert pi.invoice_date == "2026-08-10"


def test_ai_document_draft_date_ui_and_docs():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="AI document draft date"' in page
    assert 'aria-label="Create draft expense"' in page
    assert 'aria-label="Create draft purchase invoice"' in page
    assert "draftDocDate" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "AI document draft date OpenAPI" in agents
    assert "IsoDateQueryValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "AiDocumentExpenseCreate" in docs
    assert "IsoDateQueryValue" in docs
    assert "create-purchase-invoice" in docs


@pytest.mark.asyncio
async def test_ai_document_draft_date_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    blank = await ac.post(
        "/api/v1/ai/documents/create-expense",
        headers=headers,
        json={"amount": 10, "expense_date": ""},
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.post(
        "/api/v1/ai/documents/create-expense",
        headers=headers,
        json={"amount": 10, "expense_date": "not-a-date"},
    )
    assert garbage.status_code == 422, garbage.text

    slash = await ac.post(
        "/api/v1/ai/documents/create-expense",
        headers=headers,
        json={"amount": 10, "expense_date": "01/02/2024"},
    )
    assert slash.status_code == 422, slash.text

    created = await ac.post(
        "/api/v1/ai/documents/create-expense",
        headers=headers,
        json={
            "amount": 11.25,
            "payee": "Draft Date Cafe",
            "reference": "OCR-DATE-R1",
            "expense_date": "2026-08-01",
            "payment_method": "cash",
        },
    )
    assert created.status_code == 200, created.text
    exp = created.json()["data"]["expense"]
    assert float(exp["amount"]) == 11.25
    assert "2026-08-01" in str(exp.get("expense_date") or "")

    omit = await ac.post(
        "/api/v1/ai/documents/create-expense",
        headers=headers,
        json={"amount": 9.5, "payee": "Omit Date", "reference": "OCR-DATE-OMIT"},
    )
    assert omit.status_code == 200, omit.text

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={
            "name": "AI Draft Date Vendor",
            "kind": "supplier",
            "email": "ai-draft-date@example.com",
        },
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "notes": "AI draft date PI source",
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 5}],
        },
    )
    assert po.status_code == 200, po.text
    po_id = po.json()["data"]["id"]

    pi_bad = await ac.post(
        "/api/v1/ai/documents/create-purchase-invoice",
        headers=headers,
        json={"purchase_order_id": po_id, "invoice_date": "not-a-date"},
    )
    assert pi_bad.status_code == 422, pi_bad.text

    pi_blank = await ac.post(
        "/api/v1/ai/documents/create-purchase-invoice",
        headers=headers,
        json={"purchase_order_id": po_id, "invoice_date": ""},
    )
    assert pi_blank.status_code == 422, pi_blank.text

    pi_ok = await ac.post(
        "/api/v1/ai/documents/create-purchase-invoice",
        headers=headers,
        json={
            "purchase_order_id": po_id,
            "supplier_id": supplier_id,
            "supplier_invoice_number": "SUP-DATE-R1",
            "invoice_date": "2026-08-10",
        },
    )
    assert pi_ok.status_code == 200, pi_ok.text
    inv = pi_ok.json()["data"]["purchase_invoice"]
    assert inv["status"] == "draft"
    assert "2026-08-10" in str(inv.get("invoice_date") or "")
