"""Sensitive-operation audit coverage for auth, bank statements, and stock."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app.accounting import ensure_default_accounts
from tests.conftest import auth_headers


async def _super_headers(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _actions(ac, headers) -> set[str]:
    listed = await ac.get("/api/v1/audit-logs", headers=headers)
    assert listed.status_code == 200, listed.text
    return {row.get("action") for row in listed.json()["data"]}


@pytest.mark.asyncio
async def test_password_reset_request_and_confirm_audited(client, db_session):
    ac, seed = client
    req = await ac.post(
        "/api/v1/auth/password-reset-request",
        json={"email": "cashier@alpha.example.com", "tenant_id": "alpha"},
    )
    assert req.status_code == 200, req.text
    token = req.json()["data"].get("reset_token")
    assert token

    confirm = await ac.post(
        "/api/v1/auth/password-reset",
        json={"token": token, "new_password": "AnotherSecurePass123!"},
    )
    assert confirm.status_code == 200, confirm.text

    headers = await _super_headers(ac, seed)
    actions = await _actions(ac, headers)
    assert "password_reset_request" in actions
    assert "password_reset" in actions


@pytest.mark.asyncio
async def test_session_revoke_audited(client):
    ac, seed = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    sessions = await ac.get("/api/v1/auth/sessions", headers=headers)
    assert sessions.status_code == 200, sessions.text
    rows = sessions.json()["data"]
    assert rows
    target = next((s for s in rows if not s.get("current")), rows[0])
    revoked = await ac.delete(f"/api/v1/auth/sessions/{target['id']}", headers=headers)
    assert revoked.status_code == 200, revoked.text

    # Re-login so we can query audit as admin (cashier may lack audit read).
    admin = await _super_headers(ac, seed)
    actions = await _actions(ac, admin)
    assert "session_revoked" in actions


@pytest.mark.asyncio
async def test_bank_statement_create_and_import_audited(client, db_session):
    ac, seed = client
    await ensure_default_accounts(db_session, seed["t1"].id)
    bank = (
        await db_session.execute(
            select(m.Account).where(
                m.Account.tenant_id == seed["t1"].id, m.Account.code == "1010"
            )
        )
    ).scalar_one()
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    created = await ac.post(
        "/api/v1/accounting/bank-statements",
        headers=headers,
        json={
            "account_id": bank.id,
            "statement_date": "2026-08-01",
            "opening_balance": 0,
            "closing_balance": 25,
            "lines": [{"posted_at": "2026-08-01", "amount": 25, "description": "Deposit"}],
        },
    )
    assert created.status_code == 200, created.text

    csv_text = "date,amount,description,ref\n2026-08-02,10,Fee,F1\n"
    imported = await ac.post(
        "/api/v1/accounting/bank-statements/import",
        headers=headers,
        params={"account_id": bank.id, "opening_balance": 0},
        files={"file": ("stmt.csv", csv_text, "text/csv")},
    )
    assert imported.status_code == 200, imported.text

    actions = await _actions(ac, headers)
    assert "bank_statement_create" in actions
    assert "bank_statement_import" in actions


@pytest.mark.asyncio
async def test_stock_adjust_uses_hash_chained_audit(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.post(
        f"/api/v1/inventory/adjust/{seed['p1'].id}",
        headers=headers,
        json={"quantity": 2, "reason": "cycle count"},
    )
    assert r.status_code == 200, r.text

    admin = await _super_headers(ac, seed)
    listed = await ac.get(
        "/api/v1/audit-logs",
        headers=admin,
        params={"action": "stock_adjustment"},
    )
    assert listed.status_code == 200, listed.text
    rows = listed.json()["data"]
    assert rows
    assert rows[0].get("integrity_hash")
    assert rows[0].get("module") == "inventory"
    assert rows[0].get("entity_id") == seed["p1"].id
