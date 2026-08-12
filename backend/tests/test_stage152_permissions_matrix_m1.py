"""Stage 152 M1 — admin permissions matrix CSV export."""

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
async def test_permissions_matrix_export_csv(client):
    ac, seed = client
    headers = await _super(ac, seed)
    exported = await ac.get(
        "/api/v1/roles/permissions/export?active_only=false",
        headers=headers,
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "role" in header and "module" in header and "action" in header and "granted" in header
    assert "super_admin" in text or "cashier" in text or "company_admin" in text
    assert "true" in text


def test_permissions_matrix_export_ui_m1():
    page = (ROOT / "frontend/app/admin/permissions/page.tsx").read_text(encoding="utf-8")
    assert "Stage 152" in page
    assert "/roles/permissions/export" in page
    assert "Export permissions matrix CSV" in page
