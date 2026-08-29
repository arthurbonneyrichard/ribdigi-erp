"""SalesOrderConfirm.store_id ∈ UuidIdValue OpenAPI honesty (BR-7.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import SalesOrderConfirm, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_so_confirm_store_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = SalesOrderConfirm.model_validate({})
    assert omit.store_id is None
    ok = SalesOrderConfirm.model_validate({"store_id": f"  {_VALID}  "})
    assert ok.store_id == _VALID.lower()
    nullish = SalesOrderConfirm.model_validate({"store_id": None})
    assert nullish.store_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "st_001"):
        with pytest.raises(ValidationError):
            SalesOrderConfirm.model_validate({"store_id": bad})


def test_so_confirm_store_id_ui_and_docs():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Sale store"' in page
    assert "storeId.trim() || o.store_id" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Sales order confirm store_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Sale store" in docs
    assert "/confirm" in docs


@pytest.mark.asyncio
async def test_so_confirm_store_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    cust = seed["party1"].id
    item = {"product_id": seed["p1"].id, "quantity": 1, "unit_price": 8}

    created = await ac.post(
        "/api/v1/sales/orders",
        headers=headers,
        json={"customer_id": cust, "items": [item]},
    )
    assert created.status_code == 200, created.text
    order_id = created.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "st_001"):
        resp = await ac.post(
            f"/api/v1/sales/orders/{order_id}/confirm",
            headers=headers,
            json={"store_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        f"/api/v1/sales/orders/{order_id}/confirm",
        headers=headers,
        json={"store_id": f"  {str(uuid4()).upper()}  "},
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
