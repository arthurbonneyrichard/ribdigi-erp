"""PR department ∈ PurchaseRequestDepartmentValue OpenAPI (BR-6.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import (
    LowStockSuggestionsCreate,
    PurchaseRequestCreate,
    PurchaseRequestDepartmentValue,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_dept = TypeAdapter(PurchaseRequestDepartmentValue)


def test_purchase_request_department_value_schema():
    assert _dept.validate_python("  Operations  ") == "Operations"
    for bad in ("", " ", "!!!", "http://evil", "@@", "a" * 121):
        with pytest.raises(ValidationError):
            _dept.validate_python(bad)

    ok = PurchaseRequestCreate.model_validate(
        {
            "department": "  Warehouse  ",
            "items": [{"product_id": "p1", "quantity": 1}],
        }
    )
    assert ok.department == "Warehouse"
    omit = PurchaseRequestCreate.model_validate(
        {"items": [{"product_id": "p1", "quantity": 1}]}
    )
    assert omit.department is None
    with pytest.raises(ValidationError):
        PurchaseRequestCreate.model_validate(
            {"department": "!!!", "items": [{"product_id": "p1", "quantity": 1}]}
        )
    with pytest.raises(ValidationError):
        LowStockSuggestionsCreate.model_validate(
            {
                "lines": [{"product_id": "p1", "quantity": 1}],
                "department": "",
            }
        )


def test_purchase_request_department_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Purchase request department"' in page
    assert "prDepartment.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "PR department OpenAPI" in agents
    assert "PurchaseRequestDepartmentValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PurchaseRequestDepartmentValue" in docs
    assert "Purchase request department" in docs


@pytest.mark.asyncio
async def test_purchase_request_department_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]
    product_id = seed["p1"].id
    item = {"product_id": product_id, "quantity": 1}

    for bad in ("!!!", "", "http://evil.example/p"):
        r = await ac.post(
            "/api/v1/purchasing/requests",
            headers=headers,
            json={"department": bad, "items": [item]},
        )
        assert r.status_code == 422, (bad, r.text)

    hello = await ac.post(
        "/api/v1/purchasing/requests",
        headers=headers,
        json={
            "department": f"  PurchaseRequestDepartmentValue-{suffix}  ",
            "items": [item],
        },
    )
    assert hello.status_code == 200, hello.text
    assert (
        hello.json()["data"]["department"]
        == f"PurchaseRequestDepartmentValue-{suffix}"
    )

    low_bad = await ac.post(
        "/api/v1/purchasing/requests/from-low-stock",
        headers=headers,
        json={"lines": [item], "department": "!!!"},
    )
    assert low_bad.status_code == 422, low_bad.text
