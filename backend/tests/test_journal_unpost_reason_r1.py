"""Manual journal Unpost reason honesty (BR-10.2)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_journal_unpost_reason_ui_wired():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "unpostReason" in page
    assert "Required before Unpost" in page
    assert "Enter an unpost reason before unposting" in page
    assert "JSON.stringify({ reason })" in page
    assert "setUnpostReason" in page
    assert 'aria-label="Journal unpost reason"' in page
    assert "aria-label={`Unpost journal ${j.id}`}" in page
    # No silent empty-body unpost
    assert "journal-entries/${id}/unpost`, { method: 'POST', body: '{}' }" not in page


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_unpost_requires_reason_and_persists(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    assert (await ac.get("/api/v1/accounting/accounts", headers=headers)).status_code == 200

    created = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": "Unpost reason hello-world",
            "lines": [
                {"account_code": "6000", "debit": 33, "credit": 0},
                {"account_code": "1000", "debit": 0, "credit": 33},
            ],
        },
    )
    assert created.status_code == 200, created.text
    entry_id = created.json()["data"]["id"]

    missing = await ac.post(
        f"/api/v1/accounting/journal-entries/{entry_id}/unpost",
        headers=headers,
        json={},
    )
    assert missing.status_code == 422

    empty = await ac.post(
        f"/api/v1/accounting/journal-entries/{entry_id}/unpost",
        headers=headers,
        json={"reason": ""},
    )
    assert empty.status_code == 422

    blank = await ac.post(
        f"/api/v1/accounting/journal-entries/{entry_id}/unpost",
        headers=headers,
        json={"reason": "   "},
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.post(
        f"/api/v1/accounting/journal-entries/{entry_id}/unpost",
        headers=headers,
        json={"reason": "!!!!"},
    )
    assert garbage.status_code == 422, garbage.text

    no_body = await ac.post(
        f"/api/v1/accounting/journal-entries/{entry_id}/unpost",
        headers=headers,
    )
    assert no_body.status_code == 422

    ok = await ac.post(
        f"/api/v1/accounting/journal-entries/{entry_id}/unpost",
        headers=headers,
        json={"reason": "Duplicate entry — API hello-world"},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["status"] == "unposted"
    assert "Unpost: Duplicate entry — API hello-world" in (body.get("description") or "")

    audit = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.action == "journal_unposted",
                m.AuditLog.entity_id == entry_id,
            )
        )
    ).scalar_one()
    assert audit.details.get("reason") == "Duplicate entry — API hello-world"
