"""UuidIdValue OpenAPI honesty — SalesInvoiceCreate.customer_id + line product_id (BR-7.4 / BR-8.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import (
    LineItem,
    PosSaleCreate,
    SalesInvoiceCreate,
    SalesInvoiceItemCreate,
    UuidIdValue,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
_PROD = "11111111-2222-3333-4444-555555555555"
_ITEMS = [{"product_id": _PROD, "quantity": 1, "unit_price": 10}]


def test_uuid_id_value_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    assert _uuid.validate_python(_VALID.lower()) == _VALID.lower()
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "cust_001", "a b"):
        with pytest.raises(ValidationError):
            _uuid.validate_python(bad)

    ok = SalesInvoiceCreate.model_validate(
        {"customer_id": f"  {_VALID}  ", "items": _ITEMS}
    )
    assert ok.customer_id == _VALID.lower()
    assert ok.items[0].product_id == _PROD.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "cust_001"):
        with pytest.raises(ValidationError):
            SalesInvoiceCreate.model_validate({"customer_id": bad, "items": _ITEMS})
    with pytest.raises(ValidationError):
        SalesInvoiceCreate.model_validate({"items": _ITEMS})


def test_line_item_product_id_schema():
    line = LineItem.model_validate({"product_id": f"  {_PROD}  ", "quantity": 2})
    assert line.product_id == _PROD.lower()
    item = SalesInvoiceItemCreate.model_validate(
        {"product_id": f"  {_PROD.upper()}  ", "quantity": 1, "unit_price": 9}
    )
    assert item.product_id == _PROD.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "prod_001"):
        with pytest.raises(ValidationError):
            LineItem.model_validate({"product_id": bad, "quantity": 1})
        with pytest.raises(ValidationError):
            SalesInvoiceItemCreate.model_validate({"product_id": bad, "quantity": 1})
        with pytest.raises(ValidationError):
            SalesInvoiceCreate.model_validate(
                {
                    "customer_id": _VALID,
                    "items": [{"product_id": bad, "quantity": 1, "unit_price": 1}],
                }
            )
    pos = PosSaleCreate.model_validate(
        {"items": [{"product_id": f"  {_PROD}  ", "quantity": 1}], "total": 1}
    )
    assert pos.items[0].product_id == _PROD.lower()


def test_uuid_id_ui_and_docs():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Sale customer"' in page
    assert "customer_id: customerId.trim()" in page
    assert 'aria-label="Sales product"' in page
    assert "product_id: productId.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Sales invoice customer_id OpenAPI" in agents
    assert "Line item product_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "UuidIdValue" in docs
    assert "Sale customer" in docs
    assert "Sales product" in docs
    assert "items[].product_id" in docs


@pytest.mark.asyncio
async def test_uuid_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    item = {"product_id": seed["p1"].id, "quantity": 1, "unit_price": 8}
    cust = seed["party1"].id

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "cust_001"):
        resp = await ac.post(
            "/api/v1/sales/invoices",
            headers=headers,
            json={"customer_id": bad, "items": [item]},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={"customer_id": f"  {str(cust).upper()}  ", "items": [item]},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["customer_id"] == str(cust).lower()

    # Unknown but well-formed UUID → service 404 (schema accepts).
    missing = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={"customer_id": str(uuid4()), "items": [item]},
    )
    assert missing.status_code in (400, 404), missing.text


@pytest.mark.asyncio
async def test_line_item_product_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    cust = seed["party1"].id
    good_product = seed["p1"].id

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "prod_001"):
        resp = await ac.post(
            "/api/v1/sales/invoices",
            headers=headers,
            json={
                "customer_id": cust,
                "items": [{"product_id": bad, "quantity": 1, "unit_price": 8}],
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": cust,
            "items": [
                {
                    "product_id": f"  {str(good_product).upper()}  ",
                    "quantity": 1,
                    "unit_price": 8,
                }
            ],
        },
    )
    assert ok.status_code == 200, ok.text
    lines = ok.json()["data"].get("items") or ok.json()["data"].get("lines") or []
    if lines:
        assert str(lines[0].get("product_id", "")).lower() == str(good_product).lower()

    missing = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": cust,
            "items": [{"product_id": str(uuid4()), "quantity": 1, "unit_price": 8}],
        },
    )
    assert missing.status_code in (400, 404), missing.text
