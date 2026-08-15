"""Sales return reason honesty (BR-7.5) — FE/API required coded reason."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic_core import PydanticUndefined

from app.schemas import SalesReturnCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_sales_return_reason_ui_wired():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "const [returnReason, setReturnReason] = useState('');" in sales
    assert "Select a return reason" in sales
    assert "Select reason" in sales
    assert "!returnReason" in sales
    assert "useState('other')" not in sales


def test_sales_return_create_schema_no_silent_other():
    field = SalesReturnCreate.model_fields["reason"]
    assert field.is_required() or field.default is PydanticUndefined
    assert field.default is PydanticUndefined


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _posted_invoice(ac, admin, seed, *, unit_price=50.0):
    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={
            "customer_id": seed["party1"].id,
            "items": [{"product_id": seed["p1"].id, "quantity": 2, "unit_price": unit_price}],
        },
    )
    assert created.status_code == 200, created.text
    iid = created.json()["data"]["id"]
    posted = await ac.post(f"/api/v1/sales/invoices/{iid}/post", headers=admin)
    assert posted.status_code == 200, posted.text
    return posted.json()["data"]


@pytest.mark.asyncio
async def test_sales_return_reason_required(client, seeded):
    ac, seed = client
    admin = await _super(ac, seed)
    inv = await _posted_invoice(ac, admin, seed)

    omit = await ac.post(
        "/api/v1/sales/returns",
        headers=admin,
        json={
            "sales_invoice_id": inv["id"],
            "restock": False,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert omit.status_code == 422, omit.text

    blank = await ac.post(
        "/api/v1/sales/returns",
        headers=admin,
        json={
            "sales_invoice_id": inv["id"],
            "reason": "   ",
            "restock": False,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert blank.status_code == 400, blank.text
    assert "reason" in blank.text.lower()

    bad = await ac.post(
        "/api/v1/sales/returns",
        headers=admin,
        json={
            "sales_invoice_id": inv["id"],
            "reason": "not_a_reason",
            "restock": False,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert bad.status_code == 400, bad.text

    ok = await ac.post(
        "/api/v1/sales/returns",
        headers=admin,
        json={
            "sales_invoice_id": inv["id"],
            "reason": "damaged",
            "restock": False,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["reason"] == "damaged"
