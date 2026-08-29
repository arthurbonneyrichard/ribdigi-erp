"""Multi-store transfer Reject reason honesty (BR-13.2) — FE sends real reason."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app.stores import create_store
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_store_transfer_reject_reason_ui_wired():
    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert "xferRejectReason" in stores
    assert "Enter a reject reason before rejecting a store transfer" in stores
    assert "JSON.stringify({ reason: xferRejectReason.trim() })" in stores
    assert "rejection_reason" in stores
    assert "Required before Reject or Cancel" in stores
    assert 'aria-label="Stock transfer reject reason"' in stores
    reject_block_start = stores.find("Reject / Cancel reason")
    assert reject_block_start > 0
    # Reject path must not use window.prompt
    assert "window.prompt" not in stores[reject_block_start : reject_block_start + 2500]


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_stores_transfer_reject_requires_and_persists_reason(client, db_session, seeded):
    ac, seed = client
    headers = await _admin(ac, seed)

    from_store = await create_store(
        db_session, tenant_id=seed["t1"].id, name="Store Xfer From", code="SXF1"
    )
    to_store = await create_store(
        db_session, tenant_id=seed["t1"].id, name="Store Xfer To", code="SXT1"
    )
    await db_session.commit()

    created = await ac.post(
        "/api/v1/stores/transfers",
        headers=headers,
        json={
            "from_store_id": from_store.id,
            "to_store_id": to_store.id,
            "submit": True,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert created.status_code == 200, created.text
    tid = created.json()["data"]["id"]
    if created.json()["data"]["status"] == "draft":
        sub = await ac.post(f"/api/v1/stores/transfers/{tid}/submit", headers=headers)
        assert sub.status_code == 200, sub.text

    missing = await ac.post(
        f"/api/v1/stores/transfers/{tid}/reject",
        headers=headers,
        json={},
    )
    assert missing.status_code == 422, missing.text

    blank = await ac.post(
        f"/api/v1/stores/transfers/{tid}/reject",
        headers=headers,
        json={"reason": "   "},
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.post(
        f"/api/v1/stores/transfers/{tid}/reject",
        headers=headers,
        json={"reason": "!!!!"},
    )
    assert garbage.status_code == 422, garbage.text

    rejected = await ac.post(
        f"/api/v1/stores/transfers/{tid}/reject",
        headers=headers,
        json={"reason": "Wrong destination store — API hello-world"},
    )
    assert rejected.status_code == 200, rejected.text
    body = rejected.json()["data"]
    assert body["status"] == "cancelled"
    assert body["rejection_reason"] == "Wrong destination store — API hello-world"
