"""customer group code ∈ CustomerGroupCodeValue OpenAPI (BR-7.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import CustomerGroupCodeValue, CustomerGroupCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_code = TypeAdapter(CustomerGroupCodeValue)


def test_customer_group_code_value_schema():
    assert _code.validate_python("  vip-plus  ") == "vip-plus"
    for bad in ("", " ", "!!!", "http://evil", "@@", "a" * 41):
        with pytest.raises(ValidationError):
            _code.validate_python(bad)

    ok = CustomerGroupCreate.model_validate({"name": "VIP Plus", "code": "  VIP_PLUS  "})
    assert ok.code == "VIP_PLUS"
    omit = CustomerGroupCreate.model_validate({"name": "VIP Plus"})
    assert omit.code is None
    with pytest.raises(ValidationError):
        CustomerGroupCreate.model_validate({"name": "VIP Plus", "code": "!!!"})
    with pytest.raises(ValidationError):
        CustomerGroupCreate.model_validate({"name": "VIP Plus", "code": ""})


def test_customer_group_code_ui_and_docs():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Customer group code"' in sales
    assert "newGroupCode.trim() || null" in sales
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Customer group code OpenAPI" in agents
    assert "CustomerGroupCodeValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "CustomerGroupCodeValue" in docs
    assert "Customer group code" in docs


@pytest.mark.asyncio
async def test_customer_group_code_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    for bad in ("!!!", "", "http://evil.example/p"):
        r = await ac.post(
            "/api/v1/customers/groups",
            headers=headers,
            json={"name": f"TIP217 Group {suffix}", "code": bad},
        )
        assert r.status_code == 422, (bad, r.text)

    hello = await ac.post(
        "/api/v1/customers/groups",
        headers=headers,
        json={
            "name": f"TIP217 Group OK {suffix}",
            "code": f"  CG{suffix}  ",
        },
    )
    assert hello.status_code == 200, hello.text
    # service uppercases stored code
    assert hello.json()["data"]["code"] == f"CG{suffix}".upper()

    # omit code → slug from name
    omit = await ac.post(
        "/api/v1/customers/groups",
        headers=headers,
        json={"name": f"Omit Code {suffix}"},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"]["code"]
