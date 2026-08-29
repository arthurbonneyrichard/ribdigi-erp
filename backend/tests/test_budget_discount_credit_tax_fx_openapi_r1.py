"""OpenAPI honesty tips #521–#526: budget/discount/credit/tax/FX/percent rates."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import (
    CreditLimitUpdate,
    CustomerGroupCreate,
    EarlyPaySettingsUpdate,
    ExchangeRateUpsert,
    ExpenseCategoryCreate,
    NonNegativeMoneyValue,
    PercentRateValue,
    PosSaleCreate,
    PositiveMoneyValue,
    SalesInvoiceCreate,
    TaxCreate,
    TaxCalculateRequest,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_nn = TypeAdapter(NonNegativeMoneyValue)
_pct = TypeAdapter(PercentRateValue)
_pos = TypeAdapter(PositiveMoneyValue)


def test_budget_discount_credit_tax_fx_schema():
    assert _nn.validate_python(0) == 0.0
    assert _pct.validate_python(12.5) == 12.5
    assert _pos.validate_python(1.1) == 1.1
    for bad in (float("nan"), float("inf"), -1):
        with pytest.raises(ValidationError):
            _nn.validate_python(bad)
    for bad in (float("nan"), float("inf"), -1, 101):
        with pytest.raises(ValidationError):
            _pct.validate_python(bad)

    ExpenseCategoryCreate.model_validate(
        {"code": "UTIL", "name": "Utilities", "budget_amount": 100}
    )
    with pytest.raises(ValidationError):
        ExpenseCategoryCreate.model_validate(
            {"code": "UTIL", "name": "Utilities", "budget_amount": float("inf")}
        )

    SalesInvoiceCreate.model_validate(
        {
            "customer_id": str(uuid4()),
            "discount_amount": 5,
            "items": [{"product_id": str(uuid4()), "quantity": 1}],
        }
    )
    with pytest.raises(ValidationError):
        SalesInvoiceCreate.model_validate(
            {
                "customer_id": str(uuid4()),
                "discount_amount": float("nan"),
                "items": [{"product_id": str(uuid4()), "quantity": 1}],
            }
        )

    CreditLimitUpdate.model_validate({"credit_limit": 500})
    with pytest.raises(ValidationError):
        CreditLimitUpdate.model_validate({"credit_limit": -1})

    TaxCreate.model_validate({"name": "VAT", "rate": 15})
    with pytest.raises(ValidationError):
        TaxCreate.model_validate({"name": "VAT", "rate": float("inf")})

    TaxCalculateRequest.model_validate({"amount": 10, "rate": 12.5})
    with pytest.raises(ValidationError):
        TaxCalculateRequest.model_validate({"amount": 10, "rate": float("nan")})

    ExchangeRateUpsert.model_validate({"currency_code": "USD", "rate_to_base": 12.5})
    with pytest.raises(ValidationError):
        ExchangeRateUpsert.model_validate(
            {"currency_code": "USD", "rate_to_base": float("inf")}
        )

    EarlyPaySettingsUpdate.model_validate(
        {"early_pay_discount_pct": 2, "early_pay_discount_days": 10}
    )
    with pytest.raises(ValidationError):
        EarlyPaySettingsUpdate.model_validate(
            {"early_pay_discount_pct": 101, "early_pay_discount_days": 10}
        )

    CustomerGroupCreate.model_validate({"name": "VIP", "discount_percent": 5})
    with pytest.raises(ValidationError):
        CustomerGroupCreate.model_validate(
            {"name": "VIP", "discount_percent": float("nan")}
        )

    PosSaleCreate.model_validate(
        {
            "discount_amount": 1,
            "items": [{"product_id": str(uuid4()), "quantity": 1, "unit_price": 10}],
            "subtotal": 10,
            "tax": 0,
            "total": 9,
        }
    )
    with pytest.raises(ValidationError):
        PosSaleCreate.model_validate(
            {
                "discount_amount": float("inf"),
                "items": [{"product_id": str(uuid4()), "quantity": 1, "unit_price": 10}],
            }
        )


def test_budget_discount_credit_tax_fx_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Expense category budget OpenAPI",
        "Document header discount_amount OpenAPI",
        "Credit limit OpenAPI",
        "Tax rate money OpenAPI",
        "FX exchange rate OpenAPI",
        "Line discount + percent rate OpenAPI",
    ):
        assert title in agents, title
    assert "PercentRateValue" in agents

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "NonNegativeMoneyValue" in docs
    assert "PercentRateValue" in docs
    assert "PositiveMoneyValue" in docs

    exp = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Expense category monthly budget"' in exp

    credit = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Credit limit"' in credit
    assert 'aria-label="Early pay discount percent"' in credit
    assert 'aria-label="FX rate to base"' in credit

    tax = (ROOT / "frontend/app/tax/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Tax rate percent"' in tax

    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Header discount"' in sales
    assert 'aria-label="Line discount"' in sales
    assert 'aria-label="Customer group discount percent"' in sales

    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="POS cart discount"' in pos

    purch = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Purchase invoice header discount"' in purch


@pytest.mark.asyncio
async def test_budget_discount_credit_tax_fx_api_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    resp = await ac.post(
        "/api/v1/expenses/categories",
        headers=headers,
        json={"code": "BAD$", "name": "Bad", "budget_amount": "inf"},
    )
    # code may 422 first; either way money honesty is covered — use valid code
    resp = await ac.post(
        "/api/v1/expenses/categories",
        headers=headers,
        json={"code": "BADBUD", "name": "Bad Budget", "budget_amount": "inf"},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/tax/rates",
        headers=headers,
        json={"name": "Broken", "rate": "nan"},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.patch(
        "/api/v1/credit/settings",
        headers=headers,
        json={"early_pay_discount_pct": 150, "early_pay_discount_days": 10},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.put(
        "/api/v1/credit/exchange-rates/USD",
        headers=headers,
        json={"currency_code": "USD", "rate_to_base": "inf"},
    )
    assert resp.status_code == 422, resp.text

    cust = str(uuid4())
    resp = await ac.patch(
        f"/api/v1/customers/{cust}/credit-limit",
        headers=headers,
        json={"credit_limit": -1},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/customers/groups",
        headers=headers,
        json={"name": "BadPct", "discount_percent": 101},
    )
    assert resp.status_code == 422, resp.text
