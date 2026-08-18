"""PurchaseOrderCreate / PurchaseOrderAmend.delivery_address OpenAPI honesty."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import PurchaseOrderAmend, PurchaseOrderCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_po_delivery_address_schema():
    base_item = {"product_id": "p1", "quantity": 1, "unit_price": 1}
    create_omit = PurchaseOrderCreate.model_validate(
        {"supplier_id": "s1", "items": [base_item]}
    )
    assert create_omit.delivery_address is None
    create_ok = PurchaseOrderCreate.model_validate(
        {
            "supplier_id": "s1",
            "delivery_address": "  Gate B, Tema  ",
            "items": [base_item],
        }
    )
    assert create_ok.delivery_address == "Gate B, Tema"
    for bad in ("", " ", "!!!", "---", "http://addr.example", "ops@example.com"):
        with pytest.raises(ValidationError):
            PurchaseOrderCreate.model_validate(
                {"supplier_id": "s1", "delivery_address": bad, "items": [base_item]}
            )

    amend_omit = PurchaseOrderAmend.model_validate({"reason": "qty change"})
    assert amend_omit.delivery_address is None
    amend_ok = PurchaseOrderAmend.model_validate(
        {"reason": "move", "delivery_address": "Warehouse 2"}
    )
    assert amend_ok.delivery_address == "Warehouse 2"
    with pytest.raises(ValidationError):
        PurchaseOrderAmend.model_validate({"reason": "x", "delivery_address": ""})
    with pytest.raises(ValidationError):
        PurchaseOrderAmend.model_validate({"reason": "x", "delivery_address": "!!!"})


def test_po_delivery_address_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="PO delivery address"' in page
    assert 'aria-label="PO amend delivery address"' in page
    assert "AddressValue" in page or "Omit blank delivery" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "PO delivery_address OpenAPI" in agents
    assert "AddressValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PO delivery address" in docs
    assert "PO amend delivery address" in docs
    assert "AddressValue" in docs


@pytest.mark.asyncio
async def test_po_delivery_address_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "PO Address Vendor"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]
    item = {"product_id": seed["p1"].id, "quantity": 2, "unit_price": 5}

    blank = await ac.post(
        "/api/v1/purchasing/orders",
        headers=admin,
        json={
            "supplier_id": supplier_id,
            "delivery_address": "",
            "items": [item],
        },
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.post(
        "/api/v1/purchasing/orders",
        headers=admin,
        json={
            "supplier_id": supplier_id,
            "delivery_address": "!!!",
            "items": [item],
        },
    )
    assert garbage.status_code == 422, garbage.text

    ok = await ac.post(
        "/api/v1/purchasing/orders",
        headers=admin,
        json={
            "supplier_id": supplier_id,
            "delivery_address": "Gate B, Tema Wharf",
            "items": [item],
        },
    )
    assert ok.status_code == 200, ok.text
    po = ok.json()["data"]
    assert po["delivery_address"] == "Gate B, Tema Wharf"
    po_id = po["id"]

    amend_bad = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/amend",
        headers=admin,
        json={"reason": "bad ship-to", "delivery_address": "http://addr.example"},
    )
    assert amend_bad.status_code == 422, amend_bad.text

    amend_blank = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/amend",
        headers=admin,
        json={"reason": "clear ship-to", "delivery_address": ""},
    )
    assert amend_blank.status_code == 422, amend_blank.text

    amend_ok = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/amend",
        headers=admin,
        json={
            "reason": "Move to Spintex",
            "delivery_address": "Warehouse 2, Spintex Road",
        },
    )
    assert amend_ok.status_code == 200, amend_ok.text
    assert amend_ok.json()["data"]["delivery_address"] == "Warehouse 2, Spintex Road"

    amend_omit = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/amend",
        headers=admin,
        json={"reason": "qty note only", "notes": "keep ship-to"},
    )
    assert amend_omit.status_code == 200, amend_omit.text
    assert amend_omit.json()["data"]["delivery_address"] == "Warehouse 2, Spintex Road"
