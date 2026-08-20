"""PO Cancel reason honesty (BR-6.3)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_po_cancel_reason_ui_wired():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "poCancelReason" in page
    assert "Required before Cancel" in page
    assert "Enter a cancel reason before cancelling a purchase order" in page
    assert "JSON.stringify({ reason })" in page
    assert "setPoCancelReason" in page
    assert 'aria-label="Purchase order cancel reason"' in page
    assert "aria-label={`Cancel purchase order ${o.id}`}" in page


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_po_cancel_requires_reason_and_persists(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "PO Cancel Reason Vendor", "kind": "supplier"},
    )
    assert supplier.status_code == 200, supplier.text
    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "notes": "original note",
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 9}],
        },
    )
    assert created.status_code == 200, created.text
    po_id = created.json()["data"]["id"]

    missing = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/cancel",
        headers=headers,
        json={},
    )
    assert missing.status_code == 422

    empty = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/cancel",
        headers=headers,
        json={"reason": ""},
    )
    assert empty.status_code == 422

    blank = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/cancel",
        headers=headers,
        json={"reason": "   "},
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/cancel",
        headers=headers,
        json={"reason": "!!!!"},
    )
    assert garbage.status_code == 422, garbage.text

    ok = await ac.post(
        f"/api/v1/purchasing/orders/{po_id}/cancel",
        headers=headers,
        json={"reason": "Duplicate PO — API hello-world"},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["status"] == "cancelled"
    notes = body.get("notes") or ""
    assert "original note" in notes
    assert "Cancel: Duplicate PO — API hello-world" in notes

    audit = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.action == "po_cancelled",
                m.AuditLog.entity_id == po_id,
            )
        )
    ).scalar_one()
    assert audit.details.get("reason") == "Duplicate PO — API hello-world"
