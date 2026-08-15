"""Sales return condition honesty (BR-7.5) — FE/API required coded condition."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic_core import PydanticUndefined

from app.schemas import SalesReturnItemCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_sales_return_condition_ui_wired():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "const [returnCondition, setReturnCondition] = useState('');" in sales
    assert "Select a return condition" in sales
    assert "Select condition" in sales
    assert "!returnCondition" in sales
    assert "condition: returnCondition" in sales
    assert 'or ("sellable" if restock else "discard")' not in (
        ROOT / "backend/app/sales_docs.py"
    ).read_text(encoding="utf-8")


def test_sales_return_item_schema_requires_condition():
    field = SalesReturnItemCreate.model_fields["condition"]
    assert field.default is PydanticUndefined


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _posted_invoice(ac, admin, seed):
    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={
            "customer_id": seed["party1"].id,
            "items": [{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 20}],
        },
    )
    assert created.status_code == 200, created.text
    iid = created.json()["data"]["id"]
    posted = await ac.post(f"/api/v1/sales/invoices/{iid}/post", headers=admin)
    assert posted.status_code == 200, posted.text
    return posted.json()["data"]


@pytest.mark.asyncio
async def test_sales_return_condition_required_and_persisted(client, seeded):
    ac, seed = client
    admin = await _super(ac, seed)
    inv = await _posted_invoice(ac, admin, seed)

    omit = await ac.post(
        "/api/v1/sales/returns",
        headers=admin,
        json={
            "sales_invoice_id": inv["id"],
            "reason": "damaged",
            "restock": True,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert omit.status_code == 422, omit.text

    blank = await ac.post(
        "/api/v1/sales/returns",
        headers=admin,
        json={
            "sales_invoice_id": inv["id"],
            "reason": "damaged",
            "restock": True,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "condition": "  "}],
        },
    )
    assert blank.status_code == 400, blank.text
    assert "condition" in blank.text.lower()

    bad = await ac.post(
        "/api/v1/sales/returns",
        headers=admin,
        json={
            "sales_invoice_id": inv["id"],
            "reason": "damaged",
            "restock": True,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "condition": "broken"}],
        },
    )
    assert bad.status_code == 400, bad.text

    # Restock checked but condition discard — must not silently become sellable
    discard = await ac.post(
        "/api/v1/sales/returns",
        headers=admin,
        json={
            "sales_invoice_id": inv["id"],
            "reason": "defective",
            "restock": True,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "condition": "discard"}],
        },
    )
    assert discard.status_code == 200, discard.text
    body = discard.json()["data"]
    assert body["items"][0]["condition"] == "discard"
    assert body["restock"] is True
