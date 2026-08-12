"""Stage 118 F1 — fiscal period close/reopen console + mutation guards."""

from __future__ import annotations

import pyotp
import pytest

from app import accounting as accounting_svc
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_fiscal_period_close_blocks_post_and_unpost(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    await db_session.commit()

    status = await ac.get("/api/v1/accounting/fiscal-period", headers=headers)
    assert status.status_code == 200, status.text
    body = status.json()["data"]
    assert body["current_period_closed"] is False
    assert body["open_period_start"]
    assert body["open_period_end_exclusive"]

    posted = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": "Before close",
            "lines": [
                {"account_code": "6000", "debit": 12, "credit": 0},
                {"account_code": "1000", "debit": 0, "credit": 12},
            ],
        },
    )
    assert posted.status_code == 200, posted.text
    entry_id = posted.json()["data"]["id"]

    closed = await ac.post("/api/v1/accounting/fiscal-period/close", headers=headers)
    assert closed.status_code == 200, closed.text
    assert closed.json()["data"]["current_period_closed"] is True

    blocked_post = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": "After close",
            "lines": [
                {"account_code": "6000", "debit": 5, "credit": 0},
                {"account_code": "1000", "debit": 0, "credit": 5},
            ],
        },
    )
    assert blocked_post.status_code == 409, blocked_post.text
    assert blocked_post.json()["detail"]["code"] == "FISCAL_PERIOD_CLOSED"

    blocked_unpost = await ac.post(
        f"/api/v1/accounting/journal-entries/{entry_id}/unpost",
        headers=headers,
    )
    assert blocked_unpost.status_code == 409, blocked_unpost.text
    assert blocked_unpost.json()["detail"]["code"] == "FISCAL_PERIOD_CLOSED"

    reopened = await ac.post("/api/v1/accounting/fiscal-period/reopen", headers=headers)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["data"]["current_period_closed"] is False

    unposted = await ac.post(
        f"/api/v1/accounting/journal-entries/{entry_id}/unpost",
        headers=headers,
    )
    assert unposted.status_code == 200, unposted.text


def test_company_page_has_fiscal_close_console_f1():
    from pathlib import Path

    page = (Path(__file__).resolve().parents[2] / "frontend/app/company/page.tsx").read_text(
        encoding="utf-8"
    )
    assert "Stage 118" in page
    assert "/accounting/fiscal-period/close" in page
    assert "/accounting/fiscal-period/reopen" in page
    assert 'id="fiscal-period"' in page
