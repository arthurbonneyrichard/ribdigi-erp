"""Draft sales return Cancel reason honesty (BR-7.5)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_sr_cancel_reason_ui_wired():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "srCancelReason" in page
    assert "Required before Cancel" in page
    assert "Enter a cancel reason before cancelling a sales return" in page
    assert "path.includes('/returns/') && path.endsWith('/cancel')" in page
    assert "setSrCancelReason" in page
    assert 'aria-label="Sales return cancel reason"' in page
    assert "aria-label={`Cancel sales return ${r.id}`}" in page


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _posted_invoice(ac, admin, seed, *, unit_price=40.0):
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
async def test_sr_cancel_requires_reason_and_persists(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    inv = await _posted_invoice(ac, headers, seed)

    created = await ac.post(
        "/api/v1/sales/returns",
        headers=headers,
        json={
            "sales_invoice_id": inv["id"],
            "reason": "damaged",
            "restock": False,
            "notes": "original sr note",
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "condition": "discard"}],
        },
    )
    assert created.status_code == 200, created.text
    rid = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "draft"
    assert created.json()["data"]["can_cancel"] is True

    missing = await ac.post(
        f"/api/v1/sales/returns/{rid}/cancel",
        headers=headers,
        json={},
    )
    assert missing.status_code == 422

    empty = await ac.post(
        f"/api/v1/sales/returns/{rid}/cancel",
        headers=headers,
        json={"reason": ""},
    )
    assert empty.status_code == 422

    blank = await ac.post(
        f"/api/v1/sales/returns/{rid}/cancel",
        headers=headers,
        json={"reason": "   "},
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.post(
        f"/api/v1/sales/returns/{rid}/cancel",
        headers=headers,
        json={"reason": "!!!!"},
    )
    assert garbage.status_code == 422, garbage.text

    ok = await ac.post(
        f"/api/v1/sales/returns/{rid}/cancel",
        headers=headers,
        json={"reason": "Customer kept goods — API hello-world"},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["status"] == "cancelled"
    assert body["can_cancel"] is False
    notes = body.get("notes") or ""
    assert "original sr note" in notes
    assert "Cancel: Customer kept goods — API hello-world" in notes

    audit = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.action == "sales_return_cancelled",
                m.AuditLog.entity_id == rid,
            )
        )
    ).scalar_one()
    assert audit.details.get("reason") == "Customer kept goods — API hello-world"


@pytest.mark.asyncio
async def test_sr_cancel_blocked_when_not_draft(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    inv = await _posted_invoice(ac, headers, seed, unit_price=12.0)

    created = await ac.post(
        "/api/v1/sales/returns",
        headers=headers,
        json={
            "sales_invoice_id": inv["id"],
            "reason": "wrong_item",
            "restock": False,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "condition": "discard"}],
        },
    )
    assert created.status_code == 200, created.text
    rid = created.json()["data"]["id"]

    posted = await ac.post(
        f"/api/v1/sales/returns/{rid}/post",
        headers=headers,
        json={"settlement_method": "adjust"},
    )
    assert posted.status_code == 200, posted.text

    blocked = await ac.post(
        f"/api/v1/sales/returns/{rid}/cancel",
        headers=headers,
        json={"reason": "should fail after post"},
    )
    assert blocked.status_code == 409
    assert "draft" in blocked.json()["detail"].lower()
