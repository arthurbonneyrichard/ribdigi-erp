"""Stage 123 X1 — accounts / expense categories / customer groups CSV export."""

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
async def test_accounts_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={"code": "6888", "name": "Export Account 123", "account_type": "expense"},
    )
    assert created.status_code == 200, created.text

    exported = await ac.get("/api/v1/accounting/accounts/export?active_only=false", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    assert "account_type" in exported.text.splitlines()[0]
    assert "6888" in exported.text or "Export Account 123" in exported.text


@pytest.mark.asyncio
async def test_expense_categories_and_groups_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    cat = await ac.post(
        "/api/v1/expenses/categories",
        headers=headers,
        json={"code": "EXP123X", "name": "Export Exp Cat 123", "budget_amount": 50},
    )
    assert cat.status_code == 200, cat.text

    group = await ac.post(
        "/api/v1/customers/groups",
        headers=headers,
        json={"name": "Export Group 123", "discount_percent": 3},
    )
    assert group.status_code == 200, group.text

    cex = await ac.get("/api/v1/expenses/categories/export", headers=headers)
    assert cex.status_code == 200, cex.text
    assert "budget_amount" in cex.text.splitlines()[0]
    assert "EXP123X" in cex.text or "Export Exp Cat 123" in cex.text

    gex = await ac.get("/api/v1/customers/groups/export", headers=headers)
    assert gex.status_code == 200, gex.text
    assert "discount_percent" in gex.text.splitlines()[0]
    assert "Export Group 123" in gex.text


def test_finance_party_meta_export_ui_and_service_x1():
    acc = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "Stage 123" in acc
    assert "/accounting/accounts/export" in acc
    assert "Export accounts CSV" in acc
    exp = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert "/expenses/categories/export" in exp
    assert "Export expense categories CSV" in exp
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "/customers/groups/export" in sales
    assert "Export customer groups CSV" in sales
    svc = (ROOT / "backend/app/finance_meta_export.py").read_text(encoding="utf-8")
    assert "export_accounts_csv" in svc
    assert "export_expense_categories_csv" in svc
    assert "export_customer_groups_csv" in svc
