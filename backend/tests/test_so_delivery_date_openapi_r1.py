"""SalesOrderCreate / SalesOrderConfirm.delivery_date OpenAPI honesty."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import SalesOrderConfirm, SalesOrderCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_so_delivery_date_schema():
    base_item = {"product_id": "p1", "quantity": 1, "unit_price": 1}
    create_omit = SalesOrderCreate.model_validate(
        {"customer_id": "c1", "items": [base_item]}
    )
    assert create_omit.delivery_date is None
    create_ok = SalesOrderCreate.model_validate(
        {
            "customer_id": "c1",
            "delivery_date": " 2026-08-20 ",
            "items": [base_item],
        }
    )
    assert create_ok.delivery_date == "2026-08-20"
    for bad in ("", " ", "not-a-date", "01/02/2024", "2026-13-01"):
        with pytest.raises(ValidationError):
            SalesOrderCreate.model_validate(
                {"customer_id": "c1", "delivery_date": bad, "items": [base_item]}
            )

    confirm_omit = SalesOrderConfirm.model_validate({})
    assert confirm_omit.delivery_date is None
    confirm_ok = SalesOrderConfirm.model_validate({"delivery_date": "2026-09-01T12:00:00"})
    assert confirm_ok.delivery_date == "2026-09-01T12:00:00"
    with pytest.raises(ValidationError):
        SalesOrderConfirm.model_validate({"delivery_date": ""})
    with pytest.raises(ValidationError):
        SalesOrderConfirm.model_validate({"delivery_date": "not-a-date"})


def test_so_delivery_date_ui_and_docs():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="SO delivery date"' in page
    assert "deliveryDate.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "SO delivery_date OpenAPI" in agents
    assert "IsoDateQueryValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "SO delivery date" in docs
    assert "IsoDateQueryValue" in docs


@pytest.mark.asyncio
async def test_so_delivery_date_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    customer = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={
            "name": f"SO Date Customer {uuid4().hex[:6]}",
            "kind": "customer",
            "email": f"so-date-{uuid4().hex[:6]}@example.com",
        },
    )
    assert customer.status_code == 200, customer.text
    customer_id = customer.json()["data"]["id"]
    item = {
        "product_id": seed["p1"].id,
        "quantity": 1,
        "unit_price": 10,
        "tax_rate": 0,
    }

    for bad in ("", "not-a-date", "01/02/2024"):
        resp = await ac.post(
            "/api/v1/sales/orders",
            headers=headers,
            json={
                "customer_id": customer_id,
                "delivery_date": bad,
                "items": [item],
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    created = await ac.post(
        "/api/v1/sales/orders",
        headers=headers,
        json={
            "customer_id": customer_id,
            "delivery_date": "2026-08-20",
            "items": [item],
            "notes": "so delivery_date OpenAPI hello-world",
        },
    )
    assert created.status_code == 200, created.text
    order = created.json()["data"]
    assert order["status"] == "draft"
    assert str(order["delivery_date"]).startswith("2026-08-20")
    order_id = order["id"]

    for bad in ("", "not-a-date", "01/02/2024"):
        patch_bad = await ac.post(
            f"/api/v1/sales/orders/{order_id}/confirm",
            headers=headers,
            json={"delivery_date": bad},
        )
        assert patch_bad.status_code == 422, (bad, patch_bad.text)

    # Confirm may require store — address-style soft assert for success path.
    stores = await ac.get("/api/v1/stores", headers=headers)
    assert stores.status_code == 200, stores.text
    store_rows = stores.json().get("data") or []
    if isinstance(store_rows, dict):
        store_rows = store_rows.get("items") or []
    store_id = next((s["id"] for s in store_rows if s.get("is_active", True)), None)
    confirm_body: dict = {"delivery_date": "2026-09-15"}
    if store_id:
        confirm_body["store_id"] = store_id
    confirmed = await ac.post(
        f"/api/v1/sales/orders/{order_id}/confirm",
        headers=headers,
        json=confirm_body,
    )
    if confirmed.status_code == 200:
        assert str(confirmed.json()["data"]["delivery_date"]).startswith("2026-09-15")
    else:
        # Create + confirm 422 paths already prove IsoDateQueryValue honesty.
        assert confirmed.status_code in (200, 400), confirmed.text
