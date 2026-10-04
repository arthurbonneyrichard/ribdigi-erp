"""OpenAPI honesty tips #565–#570: tenant/user/org/catalog/settings body forbid."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import (
    BankAutoClearBody,
    BrandCreate,
    BranchCreate,
    CustomerGroupCreate,
    DepartmentCreate,
    LowStockSuggestionLine,
    LowStockSuggestionsCreate,
    PeriodCloseBody,
    PeriodReopenBody,
    PosPaymentLine,
    ProductCategoryCreate,
    TenantCreate,
    TenantSuspendRequest,
    UnitOfMeasureCreate,
    UserCreate,
    UserUpdate,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_ID = str(uuid4())


def test_tenant_user_catalog_settings_forbid_schema():
    TenantCreate.model_validate(
        {
            "company_name": "Tip Co",
            "slug": "tip-co-565",
            "admin_email": "admin@tip.example.com",
            "admin_password": "SecurePass123!",
        }
    )
    with pytest.raises(ValidationError):
        TenantCreate.model_validate(
            {
                "company_name": "Tip Co",
                "slug": "tip-co-565",
                "admin_email": "admin@tip.example.com",
                "admin_password": "SecurePass123!",
                "evil": 1,
            }
        )
    with pytest.raises(ValidationError):
        TenantSuspendRequest.model_validate({"reason": "Non payment", "evil": 1})

    UserCreate.model_validate(
        {
            "email": "u@tip.example.com",
            "full_name": "Tip User",
            "password": "SecurePass123!",
        }
    )
    with pytest.raises(ValidationError):
        UserCreate.model_validate(
            {
                "email": "u@tip.example.com",
                "full_name": "Tip User",
                "password": "SecurePass123!",
                "evil": 1,
            }
        )
    with pytest.raises(ValidationError):
        UserUpdate.model_validate({"full_name": "Tip", "evil": 1})

    BranchCreate.model_validate({"code": "BR1", "name": "Branch One"})
    with pytest.raises(ValidationError):
        BranchCreate.model_validate({"code": "BR1", "name": "Branch One", "evil": 1})
    DepartmentCreate.model_validate({"code": "DEP1", "name": "Sales"})
    with pytest.raises(ValidationError):
        DepartmentCreate.model_validate({"code": "DEP1", "name": "Sales", "evil": 1})

    ProductCategoryCreate.model_validate({"code": "GEN", "name": "General"})
    with pytest.raises(ValidationError):
        ProductCategoryCreate.model_validate(
            {"code": "GEN", "name": "General", "evil": 1}
        )
    BrandCreate.model_validate({"code": "ACME", "name": "Acme"})
    with pytest.raises(ValidationError):
        BrandCreate.model_validate({"code": "ACME", "name": "Acme", "evil": 1})
    UnitOfMeasureCreate.model_validate({"code": "EA", "name": "Each"})
    with pytest.raises(ValidationError):
        UnitOfMeasureCreate.model_validate({"code": "EA", "name": "Each", "evil": 1})

    CustomerGroupCreate.model_validate({"name": "Wholesale"})
    with pytest.raises(ValidationError):
        CustomerGroupCreate.model_validate({"name": "Wholesale", "evil": 1})
    LowStockSuggestionsCreate.model_validate(
        {"lines": [{"product_id": _ID, "quantity": 2}]}
    )
    with pytest.raises(ValidationError):
        LowStockSuggestionLine.model_validate(
            {"product_id": _ID, "quantity": 2, "evil": 1}
        )
    with pytest.raises(ValidationError):
        LowStockSuggestionsCreate.model_validate(
            {"lines": [{"product_id": _ID, "quantity": 2}], "evil": 1}
        )

    PeriodCloseBody.model_validate(
        {"through_date": "2024-12-31", "reason": "Year end close"}
    )
    with pytest.raises(ValidationError):
        PeriodCloseBody.model_validate(
            {"through_date": "2024-12-31", "reason": "Year end close", "evil": 1}
        )
    with pytest.raises(ValidationError):
        PeriodReopenBody.model_validate({"reason": "Correction", "evil": 1})
    BankAutoClearBody.model_validate({})
    with pytest.raises(ValidationError):
        BankAutoClearBody.model_validate({"evil": 1})
    PosPaymentLine.model_validate({"payment_method": "cash", "amount": 10})
    with pytest.raises(ValidationError):
        PosPaymentLine.model_validate(
            {"payment_method": "cash", "amount": 10, "evil": 1}
        )


def test_tenant_user_catalog_settings_forbid_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Tenant create/update bodies OpenAPI",
        "User / platform staff bodies OpenAPI",
        "Branch / department bodies OpenAPI",
        "Catalog master bodies OpenAPI",
        "Customer group / low-stock suggestion bodies OpenAPI",
        "Settings / period / POS tender line bodies OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "TenantCreate" in docs
    assert "UserCreate" in docs
    assert "BranchCreate" in docs
    assert "DepartmentCreate" in docs
    assert "ProductCategoryCreate" in docs
    assert "BrandCreate" in docs
    assert "UnitOfMeasureCreate" in docs
    assert "CustomerGroupCreate" in docs
    assert "LowStockSuggestionsCreate" in docs
    assert "PeriodCloseBody" in docs
    assert "BankAutoClearBody" in docs
    assert "PosPaymentLine" in docs and "extra=forbid" in docs


@pytest.mark.asyncio
async def test_tenant_user_catalog_settings_forbid_api_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    resp = await ac.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "tip565@alpha.example.com",
            "full_name": "Tip User",
            "password": "SecurePass123!",
            "evil": True,
        },
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={"code": "T565", "name": "Tip Branch", "evil": True},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/catalog/brands",
        headers=headers,
        json={"code": "T565", "name": "Tip Brand", "evil": True},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/customers/groups",
        headers=headers,
        json={"name": "Tip Group", "evil": True},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/accounting/period/close",
        headers=headers,
        json={
            "through_date": "2020-01-01",
            "reason": "Tip close books",
            "evil": True,
        },
    )
    assert resp.status_code == 422, resp.text
