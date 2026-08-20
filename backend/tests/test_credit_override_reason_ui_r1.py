"""Credit limit override reason honesty (BR-11.1) — no window.prompt canned defaults."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_credit_override_reason_ui_wired():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert "creditOverrideReason" in sales
    assert 'aria-label="Credit override reason"' in sales
    assert "aria-label={`Post sales invoice ${inv.id}`}" in sales
    assert "Enter a credit override reason before posting over the limit" in sales
    assert "Approved over-limit credit sale" not in sales
    assert "window.prompt('Override reason" not in sales
    assert "creditOverrideReason" in pos
    assert 'aria-label="Credit override reason"' in pos
    assert "Enter a credit override reason before completing an over-limit credit sale" in pos
    assert "Approved over-limit POS credit" not in pos
    assert "window.prompt('Override reason" not in pos


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_sales_invoice_post_override_reason_in_audit(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)

    stock = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={"product_id": seed["p1"].id, "quantity": 20},
    )
    assert stock.status_code == 200, stock.text

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Override Reason Buyer", "credit_limit": 10},
    )
    assert cust.status_code == 200, cust.text
    customer_id = cust.json()["data"]["id"]

    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 40}],
        },
    )
    assert inv.status_code == 200, inv.text
    invoice_id = inv.json()["data"]["id"]

    blocked = await ac.post(f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers, json={})
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"]["code"] == "CREDIT_LIMIT_EXCEEDED"

    no_reason = await ac.post(
        f"/api/v1/sales/invoices/{invoice_id}/post",
        headers=headers,
        json={"override_credit_limit": True},
    )
    assert no_reason.status_code == 422, no_reason.text

    blank = await ac.post(
        f"/api/v1/sales/invoices/{invoice_id}/post",
        headers=headers,
        json={"override_credit_limit": True, "override_reason": "  "},
    )
    assert blank.status_code == 422, blank.text
    assert "override_reason" in blank.text.lower()

    posted = await ac.post(
        f"/api/v1/sales/invoices/{invoice_id}/post",
        headers=headers,
        json={
            "override_credit_limit": True,
            "override_reason": "Manager approved VIP order — API hello-world",
        },
    )
    assert posted.status_code == 200, posted.text
    assert posted.json()["data"].get("credit_limit_overridden") is True

    audits = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.action == "credit_limit_override",
                m.AuditLog.entity_id == customer_id,
            )
        )
    ).scalars().all()
    assert len(audits) >= 1
    assert audits[-1].details.get("reason") == "Manager approved VIP order — API hello-world"
