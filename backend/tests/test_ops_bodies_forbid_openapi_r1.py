"""OpenAPI honesty tips #559–#564: GRN/PREQ/tax/webhook/recurring/transfer forbid."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import (
    ExpenseCategoryCreate,
    ExpenseReject,
    GrnCreate,
    GrnItemCreate,
    PurchaseRequestCreate,
    PurchaseRequestItemCreate,
    PurchaseReturnCancel,
    PurchaseReturnCreate,
    RecurringExpenseCreate,
    ReportScheduleCreate,
    SalesInvoiceCancel,
    SalesOrderCancel,
    SalesQuotationReject,
    StockTransferCreate,
    StockTransferItemCreate,
    StockTransferReject,
    TaxCalculateRequest,
    TaxCreate,
    WebhookCreate,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_ID = str(uuid4())
_ID2 = str(uuid4())


def test_ops_bodies_forbid_schema():
    GrnCreate.model_validate(
        {
            "purchase_order_id": _ID,
            "items": [{"po_item_id": _ID2, "received_qty": 1}],
        }
    )
    with pytest.raises(ValidationError):
        GrnItemCreate.model_validate(
            {"po_item_id": _ID2, "received_qty": 1, "evil": 1}
        )
    with pytest.raises(ValidationError):
        GrnCreate.model_validate(
            {
                "purchase_order_id": _ID,
                "items": [{"po_item_id": _ID2, "received_qty": 1}],
                "evil": 1,
            }
        )

    PurchaseRequestCreate.model_validate(
        {"items": [{"product_id": _ID, "quantity": 1}]}
    )
    with pytest.raises(ValidationError):
        PurchaseRequestItemCreate.model_validate(
            {"product_id": _ID, "quantity": 1, "evil": 1}
        )
    with pytest.raises(ValidationError):
        PurchaseRequestCreate.model_validate(
            {"items": [{"product_id": _ID, "quantity": 1}], "evil": 1}
        )
    PurchaseReturnCreate.model_validate(
        {
            "goods_receipt_id": _ID,
            "reason": "damaged",
            "items": [{"goods_receipt_item_id": _ID2, "quantity": 1}],
        }
    )
    with pytest.raises(ValidationError):
        PurchaseReturnCancel.model_validate({"reason": "Wrong GRN", "evil": 1})

    TaxCreate.model_validate({"name": "VAT 15", "rate": 15})
    with pytest.raises(ValidationError):
        TaxCreate.model_validate({"name": "VAT 15", "rate": 15, "evil": 1})
    TaxCalculateRequest.model_validate({"amount": 100})
    with pytest.raises(ValidationError):
        TaxCalculateRequest.model_validate({"amount": 100, "evil": 1})

    WebhookCreate.model_validate(
        {"url": "https://example.com/hook", "events": ["sale.created"]}
    )
    with pytest.raises(ValidationError):
        WebhookCreate.model_validate(
            {
                "url": "https://example.com/hook",
                "events": ["sale.created"],
                "evil": 1,
            }
        )
    ReportScheduleCreate.model_validate(
        {
            "name": "Daily sales",
            "report_type": "summary",
            "recipients": ["ops@example.com"],
        }
    )
    with pytest.raises(ValidationError):
        ReportScheduleCreate.model_validate(
            {
                "name": "Daily sales",
                "report_type": "summary",
                "recipients": ["ops@example.com"],
                "evil": 1,
            }
        )

    ExpenseCategoryCreate.model_validate({"code": "TRAVEL", "name": "Travel"})
    with pytest.raises(ValidationError):
        ExpenseCategoryCreate.model_validate(
            {"code": "TRAVEL", "name": "Travel", "evil": 1}
        )
    RecurringExpenseCreate.model_validate(
        {"amount": 50, "category": "Travel"}
    )
    with pytest.raises(ValidationError):
        RecurringExpenseCreate.model_validate(
            {"amount": 50, "category": "Travel", "evil": 1}
        )
    with pytest.raises(ValidationError):
        ExpenseReject.model_validate({"reason": "Duplicate claim", "evil": 1})

    StockTransferCreate.model_validate(
        {
            "from_store_id": _ID,
            "to_store_id": _ID2,
            "items": [{"product_id": _ID, "quantity": 1}],
        }
    )
    with pytest.raises(ValidationError):
        StockTransferItemCreate.model_validate(
            {"product_id": _ID, "quantity": 1, "evil": 1}
        )
    with pytest.raises(ValidationError):
        StockTransferCreate.model_validate(
            {
                "from_store_id": _ID,
                "to_store_id": _ID2,
                "items": [{"product_id": _ID, "quantity": 1}],
                "evil": 1,
            }
        )
    with pytest.raises(ValidationError):
        StockTransferReject.model_validate({"reason": "Wrong destination", "evil": 1})
    with pytest.raises(ValidationError):
        SalesQuotationReject.model_validate({"reason": "Price too high", "evil": 1})
    with pytest.raises(ValidationError):
        SalesOrderCancel.model_validate({"reason": "Customer cancelled", "evil": 1})
    with pytest.raises(ValidationError):
        SalesInvoiceCancel.model_validate({"reason": "Duplicate invoice", "evil": 1})


def test_ops_bodies_forbid_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "GRN create bodies OpenAPI",
        "Purchase request / return bodies OpenAPI",
        "Tax create/update/calculate bodies OpenAPI",
        "Webhook / report schedule bodies OpenAPI",
        "Recurring expense / expense category bodies OpenAPI",
        "Stock transfer / document cancel bodies OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "GrnCreate" in docs
    assert "PurchaseRequestCreate" in docs
    assert "PurchaseReturnCreate" in docs
    assert "TaxCreate" in docs
    assert "WebhookCreate" in docs
    assert "ReportScheduleCreate" in docs
    assert "RecurringExpenseCreate" in docs
    assert "ExpenseCategoryCreate" in docs
    assert "StockTransferCreate" in docs


@pytest.mark.asyncio
async def test_ops_bodies_forbid_api_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    resp = await ac.post(
        "/api/v1/purchasing/requests",
        headers=headers,
        json={"items": [{"product_id": _ID, "quantity": 1}], "evil": True},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/tax/rates",
        headers=headers,
        json={"name": "Tip561 Tax", "rate": 5, "evil": True},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/webhooks",
        headers=headers,
        json={
            "url": "https://example.com/hook",
            "events": ["sale.created"],
            "evil": True,
        },
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/expenses/categories",
        headers=headers,
        json={"code": "T561", "name": "Tip Cat", "evil": True},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/expenses/recurring",
        headers=headers,
        json={"amount": 10, "category": "Office", "evil": True},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/stores/transfers",
        headers=headers,
        json={
            "from_store_id": _ID,
            "to_store_id": _ID2,
            "items": [{"product_id": _ID, "quantity": 1}],
            "evil": True,
        },
    )
    assert resp.status_code == 422, resp.text
