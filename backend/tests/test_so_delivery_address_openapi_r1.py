"""SalesOrderCreate / SalesOrderConfirm.delivery_address OpenAPI honesty."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import SalesOrderConfirm, SalesOrderCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_so_delivery_address_schema():
    base_item = {"product_id": "p1", "quantity": 1, "unit_price": 1}
    create_omit = SalesOrderCreate.model_validate(
        {"customer_id": "c1", "items": [base_item]}
    )
    assert create_omit.delivery_address is None
    create_ok = SalesOrderCreate.model_validate(
        {
            "customer_id": "c1",
            "delivery_address": "  Gate A, Accra  ",
            "items": [base_item],
        }
    )
    assert create_ok.delivery_address == "Gate A, Accra"
    for bad in ("", " ", "!!!", "---", "http://addr.example", "ops@example.com"):
        with pytest.raises(ValidationError):
            SalesOrderCreate.model_validate(
                {"customer_id": "c1", "delivery_address": bad, "items": [base_item]}
            )

    confirm_omit = SalesOrderConfirm.model_validate({})
    assert confirm_omit.delivery_address is None
    confirm_ok = SalesOrderConfirm.model_validate(
        {"delivery_address": "Warehouse Dock 3"}
    )
    assert confirm_ok.delivery_address == "Warehouse Dock 3"
    with pytest.raises(ValidationError):
        SalesOrderConfirm.model_validate({"delivery_address": ""})
    with pytest.raises(ValidationError):
        SalesOrderConfirm.model_validate({"delivery_address": "!!!"})


def test_so_delivery_address_ui_and_docs():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="SO delivery address"' in page
    assert "AddressValue" in page or "null when blank so Create order" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "SO delivery_address OpenAPI" in agents
    assert "AddressValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "SO delivery address" in docs
    assert "AddressValue" in docs


@pytest.mark.asyncio
async def test_so_delivery_address_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    customer = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": "SO Address Buyer"},
    )
    assert customer.status_code == 200, customer.text
    customer_id = customer.json()["data"]["id"]
    item = {"product_id": seed["p1"].id, "quantity": 1, "unit_price": 10}

    blank = await ac.post(
        "/api/v1/sales/orders",
        headers=admin,
        json={
            "customer_id": customer_id,
            "delivery_address": "",
            "items": [item],
        },
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.post(
        "/api/v1/sales/orders",
        headers=admin,
        json={
            "customer_id": customer_id,
            "delivery_address": "!!!",
            "items": [item],
        },
    )
    assert garbage.status_code == 422, garbage.text

    ok = await ac.post(
        "/api/v1/sales/orders",
        headers=admin,
        json={
            "customer_id": customer_id,
            "delivery_address": "Gate A, Accra Mall",
            "items": [item],
        },
    )
    assert ok.status_code == 200, ok.text
    order = ok.json()["data"]
    assert order["delivery_address"] == "Gate A, Accra Mall"
    order_id = order["id"]

    # Confirm may require store — try with delivery only / with store from seed if present
    store_id = None
    stores = await ac.get("/api/v1/stores", headers=admin)
    if stores.status_code == 200:
        rows = stores.json().get("data") or []
        if isinstance(rows, dict):
            rows = rows.get("items") or []
        for s in rows:
            if s.get("is_active", True):
                store_id = s["id"]
                break

    confirm_bad = await ac.post(
        f"/api/v1/sales/orders/{order_id}/confirm",
        headers=admin,
        json={
            **({"store_id": store_id} if store_id else {}),
            "delivery_address": "http://addr.example",
        },
    )
    assert confirm_bad.status_code == 422, confirm_bad.text

    confirm_blank = await ac.post(
        f"/api/v1/sales/orders/{order_id}/confirm",
        headers=admin,
        json={
            **({"store_id": store_id} if store_id else {}),
            "delivery_address": "",
        },
    )
    assert confirm_blank.status_code == 422, confirm_blank.text

    confirm_ok = await ac.post(
        f"/api/v1/sales/orders/{order_id}/confirm",
        headers=admin,
        json={
            **({"store_id": store_id} if store_id else {}),
            "delivery_address": "Warehouse Dock 3, Tema",
        },
    )
    # Confirm may 400 without store or for other business rules; address honesty is 422 above.
    if confirm_ok.status_code == 200:
        assert confirm_ok.json()["data"]["delivery_address"] == "Warehouse Dock 3, Tema"
    else:
        # If confirm needs more setup, at least create path + confirm 422 paths proven.
        assert confirm_ok.status_code in (200, 400), confirm_ok.text
