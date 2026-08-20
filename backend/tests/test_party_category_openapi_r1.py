"""party category ∈ PartyCategoryValue OpenAPI (BR-6.1 / BR-7.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import PartyCategoryValue, PartyCreate, PartyUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_cat = TypeAdapter(PartyCategoryValue)


def test_party_category_value_schema():
    assert _cat.validate_python("  Wholesale  ") == "Wholesale"
    for bad in ("", " ", "!!!", "http://evil", "@@", "a" * 81):
        with pytest.raises(ValidationError):
            _cat.validate_python(bad)

    ok = PartyCreate.model_validate({"name": "Acme", "category": "  Retail  "})
    assert ok.category == "Retail"
    omit = PartyCreate.model_validate({"name": "Acme"})
    assert omit.category is None
    with pytest.raises(ValidationError):
        PartyCreate.model_validate({"name": "Acme", "category": "!!!"})
    with pytest.raises(ValidationError):
        PartyCreate.model_validate({"name": "Acme", "category": ""})

    patch_ok = PartyUpdate.model_validate({"category": " Trade "})
    assert patch_ok.category == "Trade"
    with pytest.raises(ValidationError):
        PartyUpdate.model_validate({"category": "http://x"})


def test_party_category_ui_and_docs():
    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Supplier category"' in purchasing
    assert "supplierCategory.trim() || null" in purchasing
    assert 'aria-label="Customer category"' in sales
    assert "customerCategory.trim() || null" in sales
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Party category OpenAPI" in agents
    assert "PartyCategoryValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PartyCategoryValue" in docs
    assert "Supplier category" in docs
    assert "Customer category" in docs


@pytest.mark.asyncio
async def test_party_category_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    for bad in ("!!!", "", "http://evil.example/p"):
        r = await ac.post(
            "/api/v1/suppliers",
            headers=headers,
            json={
                "name": f"TIP215 Vendor {suffix}",
                "kind": "supplier",
                "category": bad,
                "email": f"tip215-bad-{suffix}@example.com",
            },
        )
        assert r.status_code == 422, (bad, r.text)

    hello = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={
            "name": f"TIP215 Vendor OK {suffix}",
            "kind": "supplier",
            "category": f"  PartyCategoryValue-{suffix}  ",
            "email": f"tip215-ok-{suffix}@example.com",
        },
    )
    assert hello.status_code == 200, hello.text
    data = hello.json()["data"]
    assert data["category"] == f"PartyCategoryValue-{suffix}"
    supplier_id = data["id"]

    patch_bad = await ac.patch(
        f"/api/v1/suppliers/{supplier_id}",
        headers=headers,
        json={"category": "!!!"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    cust_bad = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": f"TIP215 Cust {suffix}", "category": "!!!"},
    )
    assert cust_bad.status_code == 422, cust_bad.text

    cust_ok = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={
            "name": f"TIP215 Cust OK {suffix}",
            "category": f"  Retail-{suffix}  ",
        },
    )
    assert cust_ok.status_code == 200, cust_ok.text
    assert cust_ok.json()["data"]["category"] == f"Retail-{suffix}"
