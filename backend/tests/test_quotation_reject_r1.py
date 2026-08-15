"""Quotation Reject UI + API (BR-7.2) — Accept/Reject/Convert honesty."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_quotation_reject_ui_wired():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "/sales/quotations/${q.id}/reject" in sales
    assert "Rejected" in sales
    assert "/sales/quotations/${q.id}/accept" in sales
    assert "Accept" in sales


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_quotation_reject_from_draft_and_sent(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    product = seed["p1"]

    draft = await ac.post(
        "/api/v1/sales/quotations",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "valid_days": 14,
            "items": [{"product_id": product.id, "quantity": 1, "unit_price": 10}],
        },
    )
    assert draft.status_code == 200, draft.text
    draft_id = draft.json()["data"]["id"]
    assert draft.json()["data"]["status"] == "draft"

    rejected_draft = await ac.post(
        f"/api/v1/sales/quotations/{draft_id}/reject", headers=headers
    )
    assert rejected_draft.status_code == 200, rejected_draft.text
    assert rejected_draft.json()["data"]["status"] == "rejected"

    again = await ac.post(
        f"/api/v1/sales/quotations/{draft_id}/reject", headers=headers
    )
    assert again.status_code == 409, again.text

    sent_q = await ac.post(
        "/api/v1/sales/quotations",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "valid_days": 7,
            "items": [{"product_id": product.id, "quantity": 2, "unit_price": 5}],
        },
    )
    assert sent_q.status_code == 200, sent_q.text
    sent_id = sent_q.json()["data"]["id"]

    # Avoid /send email path (audit JSON datetime quirk); mark sent directly for reject gate.
    from sqlalchemy import select

    from app import models as m

    row = (
        await db_session.execute(
            select(m.SalesQuotation).where(m.SalesQuotation.id == sent_id)
        )
    ).scalar_one()
    row.status = "sent"
    await db_session.commit()

    rejected_sent = await ac.post(
        f"/api/v1/sales/quotations/{sent_id}/reject", headers=headers
    )
    assert rejected_sent.status_code == 200, rejected_sent.text
    assert rejected_sent.json()["data"]["status"] == "rejected"

    accept_blocked = await ac.post(
        f"/api/v1/sales/quotations/{sent_id}/accept", headers=headers
    )
    assert accept_blocked.status_code == 409, accept_blocked.text
