"""Stage 120 U1 — users CSV export."""

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
async def test_users_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    exported = await ac.get("/api/v1/users/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "full_name" in header and "email" in header and "role" in header
    assert "is_active" in header
    assert "password" not in header.lower()
    assert "super@alpha.example.com" in text


def test_users_page_export_button_u1():
    page = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert "Stage 120" in page
    assert "/users/export" in page
    assert "Export users CSV" in page
    svc = (ROOT / "backend/app/user_import.py").read_text(encoding="utf-8")
    assert "export_users_csv" in svc
    assert "EXPORT_COLUMNS" in svc
