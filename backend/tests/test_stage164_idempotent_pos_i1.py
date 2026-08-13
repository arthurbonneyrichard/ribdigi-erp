"""Stage 164 I1 — POS client_request_id idempotency."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app import accounting as accounting_svc
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_pos_sale_client_request_id_replay_i1(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    await accounting_svc.ensure_default_accounts(db_session, seed["t1"].id)

    product = seed["p1"]
    product.selling_price = 10
    product.stock_qty = 20
    product.reserved_qty = 0
    product.tax_exempt = True
    product.tax_rate_id = None
    await db_session.commit()

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 20},
    )
    session_id = opened.json()["data"]["session_id"]
    body = {
        "session_id": session_id,
        "client_request_id": "idem-pos-0001",
        "items": [{"product_id": product.id, "quantity": 1}],
        "payments": [{"payment_method": "cash", "amount": 10}],
    }

    first = await ac.post("/api/v1/pos/sales", headers=headers, json=body)
    assert first.status_code == 200, first.text
    assert first.json()["data"]["replayed"] is False
    sale_id = first.json()["data"]["id"]

    second = await ac.post("/api/v1/pos/sales", headers=headers, json=body)
    assert second.status_code == 200, second.text
    assert second.json()["data"]["replayed"] is True
    assert second.json()["data"]["id"] == sale_id

    # Stock charged once
    await db_session.refresh(product)
    assert float(product.stock_qty) == 19.0


def test_pos_sale_schema_and_record_module_i1():
    schemas = (ROOT / "backend/app/schemas.py").read_text(encoding="utf-8")
    assert "client_request_id" in schemas
    assert (ROOT / "backend/app/pos_record.py").is_file()
    api = (ROOT / "backend/app/api.py").read_text(encoding="utf-8")
    assert "record_pos_sale" in api
