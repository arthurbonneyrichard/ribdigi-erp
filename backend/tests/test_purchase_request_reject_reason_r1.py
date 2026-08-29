"""Purchase request Reject reason honesty (BR-6.2) — FE + API require reason."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_purchase_request_reject_reason_ui_wired():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "prRejectReason" in page
    assert "Rejected from purchasing UI" not in page
    assert "Enter a reject reason before rejecting a purchase request" in page
    assert 'aria-label="Purchase request reject reason"' in page
    assert "rejection_reason" in page
    assert "/purchasing/requests/${id}/${action}" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "PurchaseRequestRejectReasonValue" in agents


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_purchase_request_reject_requires_reason_and_persists(client, db_session):
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

    missing = await ac.post(
        f"/api/v1/purchasing/requests/{rid}/reject",
        headers=headers,
        json={},
    )
    assert missing.status_code == 422

    empty = await ac.post(
        f"/api/v1/purchasing/requests/{rid}/reject",
        headers=headers,
        json={"reason": ""},
    )
    assert empty.status_code == 422

    blank = await ac.post(
        f"/api/v1/purchasing/requests/{rid}/reject",
        headers=headers,
        json={"reason": "   "},
    )
    # OpenAPI honesty: strip + PurchaseRequestRejectReasonValue → 422 (was service 400).
    assert blank.status_code == 422

    garbage = await ac.post(
        f"/api/v1/purchasing/requests/{rid}/reject",
        headers=headers,
        json={"reason": "!!!!"},
    )
    assert garbage.status_code == 422

    rejected = await ac.post(
        f"/api/v1/purchasing/requests/{rid}/reject",
        headers=headers,
        json={"reason": "Budget freeze Q3 — API hello-world"},
    )
    assert rejected.status_code == 200, rejected.text
    body = rejected.json()["data"]
    assert body["status"] == "rejected"
    assert body["rejection_reason"] == "Budget freeze Q3 — API hello-world"

    audit = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.action == "pr_rejected",
                m.AuditLog.entity_id == rid,
            )
        )
    ).scalar_one()
    assert audit.details.get("reason") == "Budget freeze Q3 — API hello-world"
