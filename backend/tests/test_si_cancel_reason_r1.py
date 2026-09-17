"""Draft sales invoice Cancel reason honesty (BR-7.4)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_si_cancel_reason_ui_wired():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "siCancelReason" in page
    assert "Required before Cancel" in page
    assert "Enter a cancel reason before cancelling a sales invoice" in page
    assert "path.includes('/invoices/') && path.endsWith('/cancel')" in page
    assert "setSiCancelReason" in page
    assert 'aria-label="Sales invoice cancel reason"' in page
    assert "aria-label={`Cancel sales invoice ${inv.id}`}" in page


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_si_cancel_requires_reason_and_persists(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)

    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "notes": "original si note",
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 6}],
        },
    )
    assert created.status_code == 200, created.text
    inv_id = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "draft"

    missing = await ac.post(
        f"/api/v1/sales/invoices/{inv_id}/cancel",
        headers=headers,
        json={},
    )
    assert missing.status_code == 422

    empty = await ac.post(
        f"/api/v1/sales/invoices/{inv_id}/cancel",
        headers=headers,
        json={"reason": ""},
    )
    assert empty.status_code == 422

    blank = await ac.post(
        f"/api/v1/sales/invoices/{inv_id}/cancel",
        headers=headers,
        json={"reason": "   "},
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.post(
        f"/api/v1/sales/invoices/{inv_id}/cancel",
        headers=headers,
        json={"reason": "!!!!"},
    )
    assert garbage.status_code == 422, garbage.text

    ok = await ac.post(
        f"/api/v1/sales/invoices/{inv_id}/cancel",
        headers=headers,
        json={"reason": "Duplicate invoice — API hello-world"},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["status"] == "cancelled"
    notes = body.get("notes") or ""
    assert "original si note" in notes
    assert "Cancel: Duplicate invoice — API hello-world" in notes

    audit = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.action == "invoice_cancelled",
                m.AuditLog.entity_id == inv_id,
            )
        )
    ).scalar_one()
    assert audit.details.get("reason") == "Duplicate invoice — API hello-world"


@pytest.mark.asyncio
async def test_si_cancel_blocked_when_not_draft(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)

    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 2}],
        },
    )
    assert created.status_code == 200, created.text
    inv_id = created.json()["data"]["id"]

    posted = await ac.post(
        f"/api/v1/sales/invoices/{inv_id}/post",
        headers=headers,
        json={},
    )
    assert posted.status_code == 200, posted.text

    blocked = await ac.post(
        f"/api/v1/sales/invoices/{inv_id}/cancel",
        headers=headers,
        json={"reason": "should fail after post"},
    )
    assert blocked.status_code == 409
    assert "draft" in blocked.json()["detail"].lower()
