"""party code ∈ PartyCodeValue OpenAPI (BR-6.1 / BR-7.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import PartyCodeValue, PartyCreate, PartyUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_code = TypeAdapter(PartyCodeValue)


def test_party_code_value_schema():
    assert _code.validate_python("  CUST-99  ") == "CUST-99"
    for bad in ("", " ", "!!!", "http://evil", "@@", "a" * 65):
        with pytest.raises(ValidationError):
            _code.validate_python(bad)

    ok = PartyCreate.model_validate({"name": "Acme", "code": "  C-1  "})
    assert ok.code == "C-1"
    omit = PartyCreate.model_validate({"name": "Acme"})
    assert omit.code is None
    with pytest.raises(ValidationError):
        PartyCreate.model_validate({"name": "Acme", "code": "!!!"})
    with pytest.raises(ValidationError):
        PartyCreate.model_validate({"name": "Acme", "code": ""})

    patch_ok = PartyUpdate.model_validate({"code": " SUP-2 "})
    assert patch_ok.code == "SUP-2"
    with pytest.raises(ValidationError):
        PartyUpdate.model_validate({"code": "http://x"})


def test_party_code_ui_and_docs():
    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Supplier code"' in purchasing
    assert "supplierCode.trim() || null" in purchasing
    assert 'aria-label="Customer code"' in sales
    assert "customerCode.trim() || null" in sales
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Party code OpenAPI" in agents
    assert "PartyCodeValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PartyCodeValue" in docs
    assert "Supplier code" in docs
    assert "Customer code" in docs


@pytest.mark.asyncio
async def test_party_code_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    for bad in ("!!!", "", "http://evil.example/p"):
        r = await ac.post(
            "/api/v1/suppliers",
            headers=headers,
            json={
                "name": f"TIP216 Vendor {suffix}",
                "code": bad,
                "email": f"tip216-bad-{suffix}@example.com",
            },
        )
        assert r.status_code == 422, (bad, r.text)

    hello = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={
            "name": f"TIP216 Vendor OK {suffix}",
            "code": f"  PartyCodeValue-{suffix}  ",
            "email": f"tip216-ok-{suffix}@example.com",
        },
    )
    assert hello.status_code == 200, hello.text
    data = hello.json()["data"]
    assert data["code"] == f"PartyCodeValue-{suffix}"
    supplier_id = data["id"]

    patch_bad = await ac.patch(
        f"/api/v1/suppliers/{supplier_id}",
        headers=headers,
        json={"code": "!!!"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    cust_bad = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": f"TIP216 Cust {suffix}", "code": "!!!"},
    )
    assert cust_bad.status_code == 422, cust_bad.text

    cust_ok = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={
            "name": f"TIP216 Cust OK {suffix}",
            "code": f"  C-{suffix}  ",
        },
    )
    assert cust_ok.status_code == 200, cust_ok.text
    assert cust_ok.json()["data"]["code"] == f"C-{suffix}"
