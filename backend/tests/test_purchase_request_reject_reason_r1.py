"""Purchase request Reject reason honesty (BR-6.2) — no hardcoded UI reason."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_purchase_request_reject_reason_ui_wired():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "prRejectReason" in page
    assert "Rejected from purchasing UI" not in page
    assert "Enter a reject reason before rejecting a purchase request" in page
    assert "rejection_reason" in page
    assert "/purchasing/requests/${id}/${action}" in page


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_purchase_request_reject_persists_reason(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    created = await ac.post(
        "/api/v1/purchasing/requests",
        headers=headers,
        json={
            "department": "Ops",
            "items": [{"product_id": seed["p1"].id, "quantity": 3}],
        },
    )
    assert created.status_code == 200, created.text
    rid = created.json()["data"]["id"]

    submitted = await ac.post(f"/api/v1/purchasing/requests/{rid}/submit", headers=headers)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["data"]["status"] == "pending"

    rejected = await ac.post(
        f"/api/v1/purchasing/requests/{rid}/reject",
        headers=headers,
        json={"reason": "Budget freeze Q3"},
    )
    assert rejected.status_code == 200, rejected.text
    body = rejected.json()["data"]
    assert body["status"] == "rejected"
    assert body["rejection_reason"] == "Budget freeze Q3"
