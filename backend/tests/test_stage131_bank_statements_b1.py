"""Stage 131 B1 — bank statement status honesty + CSV."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_bank_statements_status_filter_and_export(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    acct = m.Account(
        tenant_id=seed["t1"].id,
        code="1019",
        name="Stage131 Bank",
        account_type="asset",
        is_bank_account=True,
    )
    db_session.add(acct)
    await db_session.flush()

    draft = m.BankStatement(
        tenant_id=seed["t1"].id,
        account_id=acct.id,
        status="draft",
        opening_balance=0,
        closing_balance=10,
        notes="Stage131 draft",
    )
    reconciled = m.BankStatement(
        tenant_id=seed["t1"].id,
        account_id=acct.id,
        status="reconciled",
        opening_balance=0,
        closing_balance=20,
        notes="Stage131 reconciled",
    )
    db_session.add_all([draft, reconciled])
    await db_session.commit()

    bad = await ac.get(
        "/api/v1/accounting/bank-statements?status=bogus", headers=headers
    )
    assert bad.status_code == 400, bad.text

    drafts = await ac.get(
        "/api/v1/accounting/bank-statements?status=draft", headers=headers
    )
    assert drafts.status_code == 200, drafts.text
    rows = drafts.json()["data"]
    assert any(r.get("notes") == "Stage131 draft" for r in rows)
    assert all(r.get("status") == "draft" for r in rows)
    assert not any(r.get("notes") == "Stage131 reconciled" for r in rows)

    exported = await ac.get(
        "/api/v1/accounting/bank-statements/export?status=reconciled", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "status" in header and "opening_balance" in header
    assert "lines" not in header.split(",")
    assert "Stage131 reconciled" in exported.text
    assert "Stage131 draft" not in exported.text


def test_shell_and_bank_statements_b1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "statement_status=draft" in shell
    assert "statement_status=in_progress" in shell
    assert "statement_status=reconciled" in shell
    assert "Draft Statements" in shell
    assert "In Progress Statements" in shell
    assert "Reconciled Statements" in shell
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "Stage 131" in page
    assert "statementStatusFilter" in page
    assert "/accounting/bank-statements/export" in page
    assert "Export statements CSV" in page
