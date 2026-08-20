"""Sales order Cancel reason honesty (BR-7.3)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_so_cancel_reason_ui_wired():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "soCancelReason" in page
    assert "Required before Cancel" in page
    assert "Enter a cancel reason before cancelling a sales order" in page
    assert "path.includes('/orders/') && path.endsWith('/cancel')" in page
    assert "setSoCancelReason" in page
    assert 'aria-label="Sales order cancel reason"' in page
    assert "aria-label={`Cancel sales order ${o.id}`}" in page


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_so_cancel_requires_reason_and_persists(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)

    created = await ac.post(
        "/api/v1/sales/orders",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "notes": "original so note",
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 4}],
        },
    )
    assert created.status_code == 200, created.text
    oid = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "draft"
    assert created.json()["data"].get("can_cancel") is True

    missing = await ac.post(
        f"/api/v1/sales/orders/{oid}/cancel",
        headers=headers,
        json={},
    )
    assert missing.status_code == 422

    empty = await ac.post(
        f"/api/v1/sales/orders/{oid}/cancel",
        headers=headers,
        json={"reason": ""},
    )
    assert empty.status_code == 422

    blank = await ac.post(
        f"/api/v1/sales/orders/{oid}/cancel",
        headers=headers,
        json={"reason": "   "},
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.post(
        f"/api/v1/sales/orders/{oid}/cancel",
        headers=headers,
        json={"reason": "!!!!"},
    )
    assert garbage.status_code == 422, garbage.text

    ok = await ac.post(
        f"/api/v1/sales/orders/{oid}/cancel",
        headers=headers,
        json={"reason": "Duplicate order — API hello-world"},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["status"] == "cancelled"
    notes = body.get("notes") or ""
    assert "original so note" in notes
    assert "Cancel: Duplicate order — API hello-world" in notes

    audit = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.action == "so_cancelled",
                m.AuditLog.entity_id == oid,
            )
        )
    ).scalar_one()
    assert audit.details.get("reason") == "Duplicate order — API hello-world"
