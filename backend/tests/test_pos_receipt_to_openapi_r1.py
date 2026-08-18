"""POS receipt send Query `to` OpenAPI honesty (BR-8)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app.emailer import clear_dev_outbox
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_pos_receipt_to_ui_and_docs():
    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="POS receipt override to"' in pos
    assert 'aria-label="Email last receipt"' in pos
    assert 'aria-label="SMS last receipt"' in pos
    assert "receiptTo" in pos
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "POS receipt send Query `to` OpenAPI" in agents
    assert "E164PhoneValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "receipt/send" in docs
    assert "E164PhoneValue" in docs or "EmailStr" in docs


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_pos_receipt_to_blank_invalid_422(client, db_session, seeded, monkeypatch):
    ac, seed = client
    headers = await _admin(ac, seed)
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")
    clear_dev_outbox()

    product = seed["p1"]
    product.stock_qty = float(product.stock_qty or 0) + 5
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

    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": product.id, "quantity": 1, "unit_price": 10}],
        },
    )
    assert sale.status_code == 200, sale.text
    sale_id = sale.json()["data"]["id"]

    blank = await ac.post(
        f"/api/v1/pos/sales/{sale_id}/receipt/send",
        headers=headers,
        params={"channel": "email", "to": ""},
    )
    assert blank.status_code == 422, blank.text

    garbage_email = await ac.post(
        f"/api/v1/pos/sales/{sale_id}/receipt/send",
        headers=headers,
        params={"channel": "email", "to": "not-an-email"},
    )
    assert garbage_email.status_code == 422, garbage_email.text

    phone_as_email = await ac.post(
        f"/api/v1/pos/sales/{sale_id}/receipt/send",
        headers=headers,
        params={"channel": "email", "to": "+233241111111"},
    )
    assert phone_as_email.status_code == 422, phone_as_email.text

    ok_email = await ac.post(
        f"/api/v1/pos/sales/{sale_id}/receipt/send",
        headers=headers,
        params={"channel": "email", "to": "override@example.com"},
    )
    assert ok_email.status_code == 200, ok_email.text
    assert ok_email.json()["data"]["to"] == "override@example.com"
    assert ok_email.json()["data"]["channel"] == "email"

    sms_blank = await ac.post(
        f"/api/v1/pos/sales/{sale_id}/receipt/send",
        headers=headers,
        params={"channel": "sms", "to": ""},
    )
    assert sms_blank.status_code == 422, sms_blank.text

    sms_garbage = await ac.post(
        f"/api/v1/pos/sales/{sale_id}/receipt/send",
        headers=headers,
        params={"channel": "sms", "to": "not-a-phone"},
    )
    assert sms_garbage.status_code == 422, sms_garbage.text

    sms_email = await ac.post(
        f"/api/v1/pos/sales/{sale_id}/receipt/send",
        headers=headers,
        params={"channel": "sms", "to": "user@example.com"},
    )
    assert sms_email.status_code == 422, sms_email.text

    ok_sms = await ac.post(
        f"/api/v1/pos/sales/{sale_id}/receipt/send",
        headers=headers,
        params={"channel": "sms", "to": "+233241111222"},
    )
    assert ok_sms.status_code == 200, ok_sms.text
    assert ok_sms.json()["data"]["channel"] == "sms"
