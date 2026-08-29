"""ProductCreate.unit_id ∈ UuidIdValue OpenAPI honesty (BR-5.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import ProductCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_product_create_unit_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = ProductCreate.model_validate({"name": "Widget"})
    assert omit.unit_id is None
    ok = ProductCreate.model_validate(
        {"name": "Widget", "unit_id": f"  {_VALID}  "}
    )
    assert ok.unit_id == _VALID.lower()
    nullish = ProductCreate.model_validate({"name": "Widget", "unit_id": None})
    assert nullish.unit_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "unit_001", "a b"):
        with pytest.raises(ValidationError):
            ProductCreate.model_validate({"name": "Widget", "unit_id": bad})


def test_product_create_unit_id_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Product unit"' in page
    assert "unit_id: productUnitId.trim() || null" in page
    assert 'aria-label="Create product"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Product create unit_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "UuidIdValue" in docs
    assert "POST /products" in docs
    assert "Product unit" in docs


@pytest.mark.asyncio
async def test_product_create_unit_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    unit = await ac.post(
        "/api/v1/catalog/units",
        headers=headers,
        json={
            "code": f"U290{suffix[:4]}".upper(),
            "name": f"Tip290 Unit {suffix}",
        },
    )
    assert unit.status_code == 200, unit.text
    unit_id = unit.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "unit_001"):
        resp = await ac.post(
            "/api/v1/products",
            headers=headers,
            json={"name": f"Tip290 bad unit {suffix}", "unit_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": f"Tip290 with unit {suffix}",
            "unit_id": f"  {str(unit_id).upper()}  ",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["unit_id"] == str(unit_id).lower()

    missing = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={"name": f"Tip290 missing unit {suffix}", "unit_id": str(uuid4())},
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
