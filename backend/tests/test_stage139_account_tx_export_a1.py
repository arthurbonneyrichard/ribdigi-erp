"""Stage 139 A1 — account transactions CSV export."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_account_tx_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    await db_session.commit()

    cash = (
        await db_session.execute(
            select(m.Account).where(m.Account.tenant_id == tenant_id, m.Account.code == "1000")
        )
    ).scalar_one()

    created = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": "Stage139 ledger export",
            "lines": [
                {"account_code": "6000", "debit": 25, "credit": 0},
                {"account_code": "1000", "debit": 0, "credit": 25},
            ],
        },
    )
    assert created.status_code == 200, created.text
    entry_number = created.json()["data"]["entry_number"]

    exported = await ac.get(
        f"/api/v1/accounting/accounts/{cash.id}/transactions/export", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "account_code" in header and "entry_number" in header
    assert "debit" in header and "credit" in header and "balance" in header
    assert "1000" in text
    assert entry_number in text
    assert "25" in text or "25.00" in text


def test_account_tx_export_ui_a1():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "Stage 139" in page
    assert "/transactions/export" in page
    assert "Export account ledger CSV" in page
