"""OpenAPI honesty tips #553–#558: party/product/store/credit/COA/bank body forbid."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import (
    AccountCreate,
    AccountUpdate,
    BankConnectionCreate,
    BankConnectionUpdate,
    CashTransferCreate,
    ChequeLifecycleReason,
    CreditLimitOverrideBody,
    CreditLimitUpdate,
    CustomerPaymentCreate,
    OpeningBalanceCreate,
    OpeningBalanceLine,
    PartyContactCreate,
    PartyContactUpdate,
    PartyCreate,
    PartyUpdate,
    ProductCreate,
    ProductUpdate,
    StoreCreate,
    StoreUpdate,
    SupplierPaymentCreate,
    WarehouseCreate,
    WarehouseUpdate,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_AID = str(uuid4())
_CID = str(uuid4())


def test_master_credit_bank_forbid_schema():
    PartyCreate.model_validate({"name": "Acme Retail"})
    with pytest.raises(ValidationError):
        PartyCreate.model_validate({"name": "Acme Retail", "evil": 1})
    with pytest.raises(ValidationError):
        PartyUpdate.model_validate({"name": "Acme", "evil": 1})
    PartyContactCreate.model_validate({"name": "Ada Contact"})
    with pytest.raises(ValidationError):
        PartyContactCreate.model_validate({"name": "Ada Contact", "evil": 1})
    with pytest.raises(ValidationError):
        PartyContactUpdate.model_validate({"name": "Ada", "evil": 1})

    ProductCreate.model_validate({"name": "Widget"})
    with pytest.raises(ValidationError):
        ProductCreate.model_validate({"name": "Widget", "evil": 1})
    with pytest.raises(ValidationError):
        ProductUpdate.model_validate({"name": "Widget", "evil": 1})

    StoreCreate.model_validate({"code": "HQ1", "name": "Head Office"})
    with pytest.raises(ValidationError):
        StoreCreate.model_validate({"code": "HQ1", "name": "Head Office", "evil": 1})
    with pytest.raises(ValidationError):
        StoreUpdate.model_validate({"name": "HQ", "evil": 1})
    WarehouseCreate.model_validate({"code": "WH1", "name": "Main WH"})
    with pytest.raises(ValidationError):
        WarehouseCreate.model_validate({"code": "WH1", "name": "Main WH", "evil": 1})
    with pytest.raises(ValidationError):
        WarehouseUpdate.model_validate({"name": "Main", "evil": 1})

    CustomerPaymentCreate.model_validate({"customer_id": _CID, "amount": 10})
    with pytest.raises(ValidationError):
        CustomerPaymentCreate.model_validate(
            {"customer_id": _CID, "amount": 10, "evil": 1}
        )
    SupplierPaymentCreate.model_validate({"supplier_id": _CID, "amount": 10})
    with pytest.raises(ValidationError):
        SupplierPaymentCreate.model_validate(
            {"supplier_id": _CID, "amount": 10, "evil": 1}
        )
    CreditLimitUpdate.model_validate({"credit_limit": 100})
    with pytest.raises(ValidationError):
        CreditLimitUpdate.model_validate({"credit_limit": 100, "evil": 1})
    CreditLimitOverrideBody.model_validate(
        {"override_credit_limit": True, "override_reason": "Approved by manager"}
    )
    with pytest.raises(ValidationError):
        CreditLimitOverrideBody.model_validate(
            {
                "override_credit_limit": True,
                "override_reason": "Approved by manager",
                "evil": 1,
            }
        )

    AccountCreate.model_validate({"code": "1000", "name": "Cash"})
    with pytest.raises(ValidationError):
        AccountCreate.model_validate({"code": "1000", "name": "Cash", "evil": 1})
    with pytest.raises(ValidationError):
        AccountUpdate.model_validate({"name": "Cash", "evil": 1})
    OpeningBalanceCreate.model_validate(
        {"lines": [{"account_id": _AID, "amount": 1}]}
    )
    with pytest.raises(ValidationError):
        OpeningBalanceLine.model_validate(
            {"account_id": _AID, "amount": 1, "evil": 1}
        )
    with pytest.raises(ValidationError):
        OpeningBalanceCreate.model_validate(
            {"lines": [{"account_id": _AID, "amount": 1}], "evil": 1}
        )
    CashTransferCreate.model_validate(
        {"from_account_id": _AID, "to_account_id": _CID, "amount": 5}
    )
    with pytest.raises(ValidationError):
        CashTransferCreate.model_validate(
            {
                "from_account_id": _AID,
                "to_account_id": _CID,
                "amount": 5,
                "evil": 1,
            }
        )

    BankConnectionCreate.model_validate(
        {"account_id": _AID, "provider": "mock"}
    )
    with pytest.raises(ValidationError):
        BankConnectionCreate.model_validate(
            {"account_id": _AID, "provider": "mock", "evil": 1}
        )
    with pytest.raises(ValidationError):
        BankConnectionUpdate.model_validate({"display_name": "Main", "evil": 1})
    ChequeLifecycleReason.model_validate({"reason": "Insufficient funds"})
    with pytest.raises(ValidationError):
        ChequeLifecycleReason.model_validate(
            {"reason": "Insufficient funds", "evil": 1}
        )


def test_master_credit_bank_forbid_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Party create/update bodies OpenAPI",
        "Product create/update bodies OpenAPI",
        "Store / warehouse create/update bodies OpenAPI",
        "Credit payment / limit bodies OpenAPI",
        "COA / opening balance / cash transfer bodies OpenAPI",
        "Bank connection / cheque lifecycle bodies OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PartyCreate" in docs
    assert "ProductCreate" in docs
    assert "StoreCreate" in docs
    assert "WarehouseCreate" in docs
    assert "CustomerPaymentCreate" in docs
    assert "AccountCreate" in docs
    assert "CashTransferCreate" in docs
    assert "BankConnectionCreate" in docs
    assert "ChequeLifecycleReason" in docs


@pytest.mark.asyncio
async def test_master_credit_bank_forbid_api_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    resp = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Tip553 Customer", "evil": True},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "Tip554 Product", "evil": True},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={"code": "T553", "name": "Tip Store", "evil": True},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={"code": "T553", "name": "Tip Cash", "evil": True},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        f"/api/v1/customers/{_CID}/payments",
        headers=headers,
        json={"customer_id": _CID, "amount": 1, "evil": True},
    )
    assert resp.status_code == 422, resp.text
