"""PosSaleCreate.customer_name OpenAPI honesty (BR-8.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import PosSaleCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_pos_customer_name_schema():
    # Minimal body still needs items (min_length=1)
    omit = PosSaleCreate.model_validate(
        {"items": [{"product_id": "11111111-2222-3333-4444-555555555555", "quantity": 1}]}
    )
    assert omit.customer_name is None
    ok = PosSaleCreate.model_validate(
        {
            "items": [{"product_id": "11111111-2222-3333-4444-555555555555", "quantity": 1}],
            "customer_name": "  Walk-in Ada  ",
        }
    )
    assert ok.customer_name == "Walk-in Ada"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            PosSaleCreate.model_validate(
                {"items": [{"product_id": "11111111-2222-3333-4444-555555555555", "quantity": 1}], "customer_name": bad}
            )


def test_pos_customer_name_ui_and_docs():
    pos = (ROOT / "frontend/app/(dashboard)/pos/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="POS customer name"' in pos
    assert "customerName.trim()" in pos
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "POS customer_name OpenAPI" in agents
    assert "PosCustomerNameValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PosCustomerNameValue" in docs
    assert "POS customer name" in docs


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_pos_customer_name_api_blank_invalid_422(client, db_session):
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
                "payment_method": "cash",
                "customer_name": bad,
                "items": base_items,
            },
        )
        assert r.status_code == 422, (bad, r.text)

    omit = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": base_items,
        },
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"].get("customer_name") in (None, "", "Walk-in")

    suffix = uuid4().hex[:8]
    ok = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "customer_name": f"  Tip140 Guest {suffix}  ",
            "items": base_items,
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["customer_name"] == f"Tip140 Guest {suffix}"

    leftover_receipt = await ac.get(
        f"/api/v1/pos/sales/{ok.json()['data']['id']}/receipt",
        headers=headers,
    )
    assert leftover_receipt.status_code == 200, leftover_receipt.text
    leftover_data = leftover_receipt.json()["data"]
    leftover_text = leftover_data.get("text") or ""
    leftover_html = leftover_data.get("html") or ""
    assert leftover_data.get("customer_name") == "Walk-in"
    assert "Walk-in" in leftover_text
    assert f"Tip140 Guest {suffix}" not in leftover_text
    assert f"Tip140 Guest {suffix}" not in leftover_html

    omit_receipt = await ac.get(
        f"/api/v1/pos/sales/{omit.json()['data']['id']}/receipt",
        headers=headers,
    )
    assert omit_receipt.status_code == 200, omit_receipt.text
    assert "Walk-in" in (omit_receipt.json()["data"].get("text") or "")

    customer = seed["party1"]
    named = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "party_id": customer.id,
            "customer_name": "Leftover Till Name",
            "items": base_items,
        },
    )
    assert named.status_code == 200, named.text
    assert named.json()["data"]["customer_name"] == customer.name
    selected_receipt = await ac.get(
        f"/api/v1/pos/sales/{named.json()['data']['id']}/receipt",
        headers=headers,
    )
    assert selected_receipt.status_code == 200, selected_receipt.text
    selected_text = selected_receipt.json()["data"].get("text") or ""
    assert customer.name in selected_text
    assert "Leftover Till Name" not in selected_text
