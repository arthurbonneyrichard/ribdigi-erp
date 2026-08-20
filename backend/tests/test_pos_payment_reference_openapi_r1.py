"""PosPaymentLine.reference OpenAPI honesty (BR-8.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import PosPaymentLine, PosSaleCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_pos_payment_reference_schema():
    omit = PosPaymentLine.model_validate({"payment_method": "card", "amount": 10})
    assert omit.reference is None
    ok = PosPaymentLine.model_validate(
        {"payment_method": "card", "amount": 10, "reference": "  AUTH-99  "}
    )
    assert ok.reference == "AUTH-99"
    for bad in ("", " ", "!!!", "!!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            PosPaymentLine.model_validate(
                {"payment_method": "card", "amount": 10, "reference": bad}
            )

    sale_ok = PosSaleCreate.model_validate(
        {
            "items": [{"product_id": "p1", "quantity": 1}],
            "payment_method": "card",
            "payments": [
                {"payment_method": "card", "amount": 10, "reference": "  TIP185  "}
            ],
        }
    )
    assert sale_ok.payments and sale_ok.payments[0].reference == "TIP185"
    with pytest.raises(ValidationError):
        PosSaleCreate.model_validate(
            {
                "items": [{"product_id": "p1", "quantity": 1}],
                "payments": [
                    {"payment_method": "card", "amount": 10, "reference": "!!!!"}
                ],
            }
        )


def test_pos_payment_reference_ui_and_docs():
    page = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="POS payment reference"' in page
    assert "paymentReference.trim() || null" in page
    assert 'aria-label="Charge complete sale"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "PosPaymentLine.reference" in agents
    assert "PaymentReferenceValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PosPaymentLine.reference" in docs
    assert "POS payment reference" in docs


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_pos_payment_reference_api_blank_invalid_422(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    product = seed["p1"]
    product.stock_qty = float(product.stock_qty or 0) + 20
    product.selling_price = 10
    await db_session.commit()

    cur = await ac.get("/api/v1/pos/sessions/current", headers=headers)
    if cur.status_code == 200 and cur.json().get("data"):
        sid = cur.json()["data"].get("session_id") or cur.json()["data"].get("id")
        if sid:
            await ac.post(
                f"/api/v1/pos/sessions/{sid}/close",
                headers=headers,
                json={"actual_cash": 0},
            )

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 20},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"].get("session_id") or opened.json()["data"]["id"]

    base_items = [{"product_id": product.id, "quantity": 1, "unit_price": 10}]
    for bad in ("", "!!!", "http://evil"):
        r = await ac.post(
            "/api/v1/pos/sales",
            headers=headers,
            json={
                "session_id": session_id,
                "payment_method": "card",
                "items": base_items,
                "payments": [
                    {"payment_method": "card", "amount": 10, "reference": bad},
                ],
            },
        )
        assert r.status_code == 422, (bad, r.text)

    suffix = uuid4().hex[:8]
    tag = f"TIP185-{suffix}"
    ok = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": session_id,
            "payment_method": "card",
            "items": base_items,
            "payments": [
                {"payment_method": "card", "amount": 10, "reference": f"  {tag}  "},
            ],
        },
    )
    assert ok.status_code == 200, ok.text
    data = ok.json().get("data") or {}
    payments = data.get("payments") or []
    assert payments, data
    assert payments[0].get("reference") == tag, data
