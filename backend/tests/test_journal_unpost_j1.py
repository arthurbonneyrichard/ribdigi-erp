"""Manual journal unpost + attachments (BR-10.2)."""

from __future__ import annotations

from datetime import datetime, timedelta
from io import BytesIO

import pyotp
import pytest

from app.accounting import (
    fiscal_period_bounds,
    in_current_fiscal_period,
    post_journal_entry,
)
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_fiscal_period_bounds_calendar_year():
    start, end = fiscal_period_bounds("01-01", as_of=datetime(2026, 8, 13).date())
    assert start == datetime(2026, 1, 1)
    assert end == datetime(2027, 1, 1)
    assert in_current_fiscal_period(datetime(2026, 6, 1), "01-01", as_of=datetime(2026, 8, 13).date())
    assert not in_current_fiscal_period(
        datetime(2025, 12, 31), "01-01", as_of=datetime(2026, 8, 13).date()
    )


def test_fiscal_period_bounds_april_year():
    start, end = fiscal_period_bounds("04-01", as_of=datetime(2026, 2, 1).date())
    assert start == datetime(2025, 4, 1)
    assert end == datetime(2026, 4, 1)


@pytest.mark.asyncio
async def test_unpost_manual_journal_reverses_balances(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)

    # Seed COA
    assert (await ac.get("/api/v1/accounting/accounts", headers=headers)).status_code == 200

    before = await ac.get("/api/v1/accounting/accounts", headers=headers)
    cash0 = next(a for a in before.json()["data"] if a["code"] == "1000")
    exp0 = next(a for a in before.json()["data"] if a["code"] == "6000")
    cash_bal0 = float(cash0["balance"])
    exp_bal0 = float(exp0["balance"])

    r = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": "Adjusting entry for unpost test",
            "lines": [
                {"account_code": "6000", "debit": 75, "credit": 0},
                {"account_code": "1000", "debit": 0, "credit": 75},
            ],
        },
    )
    assert r.status_code == 200, r.text
    entry = r.json()["data"]
    assert entry["status"] == "posted"
    assert entry["can_unpost"] is True
    entry_id = entry["id"]

    mid = await ac.get("/api/v1/accounting/accounts", headers=headers)
    cash1 = next(a for a in mid.json()["data"] if a["code"] == "1000")
    exp1 = next(a for a in mid.json()["data"] if a["code"] == "6000")
    assert abs(float(exp1["balance"]) - (exp_bal0 + 75)) < 0.01
    assert abs(float(cash1["balance"]) - (cash_bal0 - 75)) < 0.01

    u = await ac.post(
        f"/api/v1/accounting/journal-entries/{entry_id}/unpost",
        headers=headers,
        json={"reason": "Correction — wrong account"},
    )
    assert u.status_code == 200, u.text
    assert u.json()["data"]["status"] == "unposted"
    assert u.json()["data"]["can_unpost"] is False
    assert "Unpost: Correction — wrong account" in (u.json()["data"].get("description") or "")

    after = await ac.get("/api/v1/accounting/accounts", headers=headers)
    cash2 = next(a for a in after.json()["data"] if a["code"] == "1000")
    exp2 = next(a for a in after.json()["data"] if a["code"] == "6000")
    assert abs(float(cash2["balance"]) - cash_bal0) < 0.01
    assert abs(float(exp2["balance"]) - exp_bal0) < 0.01

    again = await ac.post(
        f"/api/v1/accounting/journal-entries/{entry_id}/unpost",
        headers=headers,
        json={"reason": "retry"},
    )
    assert again.status_code == 400


@pytest.mark.asyncio
async def test_unpost_blocks_auto_source_journals(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    assert (await ac.get("/api/v1/accounting/accounts", headers=headers)).status_code == 200

    entry = await post_journal_entry(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["u1"].id,
        description="System invoice JE",
        lines=[
            {"account_code": "1100", "debit": 10, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 10},
        ],
        source_type="sales_invoice",
        source_id="inv-x",
    )
    await db_session.commit()

    r = await ac.post(
        f"/api/v1/accounting/journal-entries/{entry.id}/unpost",
        headers=headers,
        json={"reason": "should fail — auto source"},
    )
    assert r.status_code == 400
    assert "manual" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_unpost_blocks_outside_fiscal_period(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    assert (await ac.get("/api/v1/accounting/accounts", headers=headers)).status_code == 200

    entry = await post_journal_entry(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["u1"].id,
        description="Prior-year manual",
        lines=[
            {"account_code": "6000", "debit": 5, "credit": 0},
            {"account_code": "1000", "debit": 0, "credit": 5},
        ],
    )
    # Force entry date into prior fiscal year (tenant default 01-01)
    entry.entry_date = datetime.utcnow() - timedelta(days=400)
    await db_session.commit()

    r = await ac.post(
        f"/api/v1/accounting/journal-entries/{entry.id}/unpost",
        headers=headers,
        json={"reason": "should fail — prior year"},
    )
    assert r.status_code == 400
    assert "fiscal" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_journal_attachment_upload_download_delete(client, db_session, tmp_path, monkeypatch):
    from app import storage as storage_svc

    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    ac, seed = client
    headers = await _admin(ac, seed)
    assert (await ac.get("/api/v1/accounting/accounts", headers=headers)).status_code == 200

    r = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": "With attachment",
            "lines": [
                {"account_code": "6000", "debit": 12, "credit": 0},
                {"account_code": "1000", "debit": 0, "credit": 12},
            ],
        },
    )
    assert r.status_code == 200, r.text
    entry_id = r.json()["data"]["id"]

    up = await ac.post(
        f"/api/v1/accounting/journal-entries/{entry_id}/attachment",
        headers=headers,
        files={"file": ("voucher.pdf", BytesIO(b"%PDF-1.4 journal-voucher"), "application/pdf")},
    )
    assert up.status_code == 200, up.text
    assert up.json()["data"]["has_attachment"] is True

    dl = await ac.get(
        f"/api/v1/accounting/journal-entries/{entry_id}/attachment", headers=headers
    )
    assert dl.status_code == 200
    assert dl.content.startswith(b"%PDF")

    rm = await ac.delete(
        f"/api/v1/accounting/journal-entries/{entry_id}/attachment", headers=headers
    )
    assert rm.status_code == 200
    assert rm.json()["data"]["has_attachment"] is False


@pytest.mark.asyncio
async def test_unpost_requires_accounting_write(client):
    ac, seed = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    r = await ac.post(
        "/api/v1/accounting/journal-entries/x/unpost",
        headers=headers,
        json={"reason": "nope"},
    )
    assert r.status_code == 403
