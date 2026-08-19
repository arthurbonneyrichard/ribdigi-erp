"""Stage 18 T1: launch checklist §4 smoke — expense→JE, TB/P&L, backup verify/dry-run."""

from __future__ import annotations

from datetime import datetime

import pyotp
import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import models as m
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_launch_expense_to_journal_tb_pnl_and_backup_drill(
    client, db_session, tmp_path, monkeypatch
):
    """LAUNCH_CHECKLIST §4: expense→JE, TB/P&L readable, backup create→verify→dry-run."""
    ac, seed = client
    mgr = await _mgr(ac)
    super_h = await _super(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    await db_session.commit()

    # --- Expense create → (auto)approve → journal ---
    cat = await ac.post(
        "/api/v1/expenses/categories",
        headers=mgr,
        json={"code": "S18T1EXP", "name": "S18 T1 Ops", "budget_amount": 0},
    )
    assert cat.status_code == 200, cat.text
    category_id = cat.json()["data"]["id"]

    created = await ac.post(
        "/api/v1/expenses",
        headers=mgr,
        json={
            "category_id": category_id,
            "amount": 42.5,
            "description": "Stage 18 T1 launch smoke expense",
            "payment_method": "cash",
            "payee": "Ops Vendor",
        },
    )
    assert created.status_code == 200, created.text
    expense = created.json()["data"]
    assert expense["status"] == "approved"
    expense_id = expense["id"]

    je = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.source_type == "expense",
                m.JournalEntry.source_id == expense_id,
            )
        )
    ).scalar_one_or_none()
    assert je is not None
    assert float(je.total_debit) == pytest.approx(float(je.total_credit))
    assert float(je.total_debit) == pytest.approx(42.5)

    # --- Trial balance / P&L readable ---
    tb = await ac.get("/api/v1/accounting/trial-balance", headers=super_h)
    assert tb.status_code == 200, tb.text
    tdata = tb.json()["data"]
    assert tdata["balanced"] is True
    assert float(tdata["total_debit"]) == pytest.approx(float(tdata["total_credit"]))

    today = datetime.utcnow().strftime("%Y-%m-%d")
    pnl = await ac.get(
        "/api/v1/accounting/profit-loss",
        headers=super_h,
        params={"from_date": today, "to_date": today},
    )
    assert pnl.status_code == 200, pnl.text
    assert "operating_expenses" in pnl.json()["data"]
    assert float(pnl.json()["data"]["operating_expenses"]) >= 42.5

    # --- Backup create → verify → dry-run restore ---
    monkeypatch.setattr("app.backup.settings.BACKUP_DIR", str(tmp_path))
    monkeypatch.setattr("app.backup.settings.BACKUP_ENCRYPTION_KEY", "")
    monkeypatch.setattr("app.config.settings.BACKUP_DIR", str(tmp_path))

    backup_h = {**super_h, "X-Workspace-Kind": "tenant"}
    backup = await ac.post(
        "/api/v1/backup", headers=backup_h, json={"notes": "s18-t1-launch-smoke"}
    )
    assert backup.status_code == 200, backup.text
    backup_id = backup.json()["data"]["id"]
    assert backup.json()["data"]["checksum_sha256"]

    verify = await ac.post(
        f"/api/v1/backup/{backup_id}/verify",
        headers=backup_h,
        json={"sample_limit": 25},
    )
    assert verify.status_code == 200, verify.text
    assert verify.json()["data"]["proof"]["ok"] is True

    dry = await ac.post(
        f"/api/v1/backup/{backup_id}/restore",
        headers=backup_h,
        json={"dry_run": True},
    )
    assert dry.status_code == 200, dry.text
    assert dry.json()["data"]["valid"] is True
    assert dry.json()["data"]["dry_run"] is True
    assert dry.json()["data"]["applied"] is False

    # Guard: accidental apply without RESTORE text is blocked
    blocked = await ac.post(
        f"/api/v1/backup/{backup_id}/restore",
        headers=backup_h,
        json={"dry_run": False, "confirm": True, "confirm_text": "YES"},
    )
    assert blocked.status_code == 400
