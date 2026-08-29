"""Period close / reopen reason honesty (BR-10.2)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_period_close_reason_ui_wired():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "periodReason" in page
    assert "Required close / reopen reason" in page
    assert 'aria-label="Period close or reopen reason"' in page
    assert 'aria-label="Close books"' in page
    assert 'aria-label="Reopen books"' in page
    assert "Enter a close reason before closing the books" in page
    assert "Enter a reopen reason before reopening the books" in page
    assert "through_date: closeThrough, reason" in page


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_period_close_and_reopen_require_reason(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    yesterday = (datetime.utcnow().date() - timedelta(days=1)).isoformat()

    missing = await ac.post(
        "/api/v1/accounting/period/close",
        headers=headers,
        json={"through_date": yesterday},
    )
    assert missing.status_code == 422

    empty = await ac.post(
        "/api/v1/accounting/period/close",
        headers=headers,
        json={"through_date": yesterday, "reason": ""},
    )
    assert empty.status_code == 422

    blank = await ac.post(
        "/api/v1/accounting/period/close",
        headers=headers,
        json={"through_date": yesterday, "reason": "   "},
    )
    assert blank.status_code == 422

    ok = await ac.post(
        "/api/v1/accounting/period/close",
        headers=headers,
        json={"through_date": yesterday, "reason": "Month-end close — API hello-world"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["books_closed_through"] == yesterday

    close_audit = (
        await db_session.execute(
            select(m.AuditLog)
            .where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.action == "period_closed",
            )
            .order_by(m.AuditLog.created_at.desc())
        )
    ).scalars().first()
    assert close_audit is not None
    assert close_audit.details.get("reason") == "Month-end close — API hello-world"

    reopen_missing = await ac.post(
        "/api/v1/accounting/period/reopen",
        headers=headers,
        json={"through_date": None},
    )
    assert reopen_missing.status_code == 422

    reopen_blank = await ac.post(
        "/api/v1/accounting/period/reopen",
        headers=headers,
        json={"through_date": None, "reason": "  "},
    )
    assert reopen_blank.status_code == 422

    reopen = await ac.post(
        "/api/v1/accounting/period/reopen",
        headers=headers,
        json={"through_date": None, "reason": "Correction after close — API hello-world"},
    )
    assert reopen.status_code == 200, reopen.text
    assert reopen.json()["data"]["books_closed_through"] is None

    reopen_audit = (
        await db_session.execute(
            select(m.AuditLog)
            .where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.action == "period_reopened",
            )
            .order_by(m.AuditLog.created_at.desc())
        )
    ).scalars().first()
    assert reopen_audit is not None
    assert reopen_audit.details.get("reason") == "Correction after close — API hello-world"
