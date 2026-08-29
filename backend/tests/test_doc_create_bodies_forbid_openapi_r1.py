"""OpenAPI honesty tips #547–#552: sales/purchasing/expense/journal body forbid."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import (
    ExpenseCreate,
    ExpenseUpdate,
    JournalCreate,
    JournalLineCreate,
    PurchaseInvoiceCreate,
    PurchaseInvoiceItemCreate,
    PurchaseInvoiceUpdate,
    PurchaseOrderAmend,
    PurchaseOrderCreate,
    PurchaseOrderItemCreate,
    SalesInvoiceCreate,
    SalesOrderCreate,
    SalesQuotationCreate,
    SalesReturnCreate,
    SalesReturnItemCreate,
    SalesReturnPost,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_PID = str(uuid4())
_CID = str(uuid4())
_SID = str(uuid4())
_ITEM = {"product_id": _PID, "quantity": 1}
_PO_ITEM = {"product_id": _PID, "quantity": 1, "unit_price": 10}


def test_doc_create_bodies_forbid_schema():
    SalesInvoiceCreate.model_validate({"customer_id": _CID, "items": [_ITEM]})
    with pytest.raises(ValidationError):
        SalesInvoiceCreate.model_validate(
            {"customer_id": _CID, "items": [_ITEM], "evil": 1}
        )
    with pytest.raises(ValidationError):
        SalesQuotationCreate.model_validate(
            {"customer_id": _CID, "items": [_ITEM], "evil": 1}
        )
    with pytest.raises(ValidationError):
        SalesOrderCreate.model_validate(
            {"customer_id": _CID, "items": [_ITEM], "evil": 1}
        )

    SalesReturnCreate.model_validate(
        {
            "sales_invoice_id": _CID,
            "reason": "damaged",
            "items": [
                {
                    "product_id": _PID,
                    "quantity": 1,
                    "condition": "sellable",
                }
            ],
        }
    )
    with pytest.raises(ValidationError):
        SalesReturnItemCreate.model_validate(
            {
                "product_id": _PID,
                "quantity": 1,
                "condition": "sellable",
                "evil": 1,
            }
        )
    with pytest.raises(ValidationError):
        SalesReturnPost.model_validate({"settlement_method": "adjust", "x": 1})

    PurchaseOrderCreate.model_validate(
        {"supplier_id": _SID, "items": [_PO_ITEM]}
    )
    with pytest.raises(ValidationError):
        PurchaseOrderItemCreate.model_validate({**_PO_ITEM, "evil": 1})
    with pytest.raises(ValidationError):
        PurchaseOrderCreate.model_validate(
            {"supplier_id": _SID, "items": [_PO_ITEM], "evil": 1}
        )
    with pytest.raises(ValidationError):
        PurchaseOrderAmend.model_validate({"reason": "Price change", "evil": 1})

    PurchaseInvoiceCreate.model_validate({"supplier_id": _SID, "items": [_ITEM]})
    with pytest.raises(ValidationError):
        PurchaseInvoiceItemCreate.model_validate({**_ITEM, "evil": 1})
    with pytest.raises(ValidationError):
        PurchaseInvoiceCreate.model_validate(
            {"supplier_id": _SID, "items": [_ITEM], "evil": 1}
        )
    with pytest.raises(ValidationError):
        PurchaseInvoiceUpdate.model_validate({"notes": "ok", "evil": 1})

    ExpenseCreate.model_validate({"amount": 10, "category": "Travel"})
    with pytest.raises(ValidationError):
        ExpenseCreate.model_validate(
            {"amount": 10, "category": "Travel", "evil": 1}
        )
    with pytest.raises(ValidationError):
        ExpenseUpdate.model_validate({"amount": 12, "evil": 1})

    JournalCreate.model_validate(
        {
            "description": "Month end accrual",
            "lines": [
                {"account_code": "1000", "debit": 10, "credit": 0},
                {"account_code": "2000", "debit": 0, "credit": 10},
            ],
        }
    )
    with pytest.raises(ValidationError):
        JournalLineCreate.model_validate(
            {"account_code": "1000", "debit": 1, "credit": 0, "evil": 1}
        )
    with pytest.raises(ValidationError):
        JournalCreate.model_validate(
            {
                "description": "Month end accrual",
                "lines": [
                    {"account_code": "1000", "debit": 10, "credit": 0},
                    {"account_code": "2000", "debit": 0, "credit": 10},
                ],
                "evil": 1,
            }
        )


def test_doc_create_bodies_forbid_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Sales document create bodies OpenAPI",
        "Sales return create bodies OpenAPI",
        "Purchase order create bodies OpenAPI",
        "Purchase invoice create bodies OpenAPI",
        "Expense create/update bodies OpenAPI",
        "Journal create bodies OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "SalesInvoiceCreate" in docs
    assert "PurchaseOrderCreate" in docs
    assert "PurchaseInvoiceCreate" in docs
    assert "ExpenseCreate" in docs
    assert "JournalCreate" in docs
    assert "SalesReturnCreate" in docs


@pytest.mark.asyncio
async def test_doc_create_bodies_forbid_api_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    resp = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={"customer_id": _CID, "items": [_ITEM], "evil": True},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={"supplier_id": _SID, "items": [_PO_ITEM], "evil": True},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={"amount": 5, "category": "Office", "evil": True},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": "Test journal entry",
            "lines": [
                {"account_code": "1000", "debit": 1, "credit": 0},
                {"account_code": "2000", "debit": 0, "credit": 1},
            ],
            "evil": True,
        },
    )
    assert resp.status_code == 422, resp.text
