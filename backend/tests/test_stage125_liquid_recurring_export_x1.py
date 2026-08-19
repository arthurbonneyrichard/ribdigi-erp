"""Stage 125 X1 — liquid accounts / recurring expenses CSV export."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_liquid_accounts_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/accounting/liquid-accounts",
        headers=headers,
        json={
            "kind": "bank",
            "code": "1088",
            "name": "Export Bank 125",
            "bank_name": "Stage125 Bank",
            "account_number": "9999",
            "bank_branch": "Main",
        },
    )
    assert created.status_code == 200, created.text

    exported = await ac.get(
        "/api/v1/accounting/liquid-accounts/export?active_only=false", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "bank_name" in header and "is_active" in header
    assert "1088" in exported.text or "Export Bank 125" in exported.text
    assert "Stage125 Bank" in exported.text


@pytest.mark.asyncio
async def test_recurring_expenses_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/expenses/recurring",
        headers=headers,
        json={
            "amount": 15,
            "frequency": "weekly",
            "description": "Export Recurring 125",
            "payment_method": "cash",
            "category": "utilities",
        },
    )
    assert created.status_code == 200, created.text

    exported = await ac.get("/api/v1/expenses/recurring/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "frequency" in header and "is_active" in header
    assert "Export Recurring 125" in exported.text


def test_liquid_recurring_export_ui_and_service_x1():
    acc = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "Stage 125" in acc
    assert "/accounting/liquid-accounts/export" in acc
    assert "Export liquid accounts CSV" in acc
    exp = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert "/expenses/recurring/export" in exp
    assert "Export recurring CSV" in exp
    svc = (ROOT / "backend/app/liquid_recurring_export.py").read_text(encoding="utf-8")
    assert "export_liquid_accounts_csv" in svc
    assert "export_recurring_expenses_csv" in svc
