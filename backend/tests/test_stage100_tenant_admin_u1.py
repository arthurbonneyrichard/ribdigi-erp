"""Stage 100 U1 — Tenant admin discovery honesty."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_users_and_audit_ui_url_sync_u1():
    users = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert "useSearchParams" in users
    assert "is_active" in users
    assert "syncUrl" in users
    assert "roleFilter" in users or "role" in users

    audit = (ROOT / "frontend/app/audit/page.tsx").read_text(encoding="utf-8")
    assert "useSearchParams" in audit
    assert "syncUrl" in audit
    assert "module" in audit and "action" in audit


@pytest.mark.asyncio
async def test_tenant_users_q_role_is_active_filters(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    all_users = await ac.get("/api/v1/users", headers=headers)
    assert all_users.status_code == 200, all_users.text
    data = all_users.json().get("data") or []
    assert data, "seed should include tenant users"

    sample = data[0]
    email_token = (sample.get("email") or "").split("@")[0]
    assert email_token

    by_q = await ac.get(f"/api/v1/users?q={email_token}", headers=headers)
    assert by_q.status_code == 200, by_q.text
    emails = {u["email"] for u in by_q.json().get("data") or []}
    assert sample["email"] in emails

    role = sample.get("role") or "company_admin"
    by_role = await ac.get(f"/api/v1/users?role={role}", headers=headers)
    assert by_role.status_code == 200, by_role.text
    assert all(u["role"] == role for u in by_role.json().get("data") or [])

    active = await ac.get("/api/v1/users?is_active=true", headers=headers)
    assert active.status_code == 200, active.text
    assert all(u["is_active"] is True for u in active.json().get("data") or [])

    inactive = await ac.get("/api/v1/users?is_active=false", headers=headers)
    assert inactive.status_code == 200, inactive.text
    assert all(u["is_active"] is False for u in inactive.json().get("data") or [])
