"""Stage 140 S1 — storage settings CSV export (secret-free)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _admin(ac, seed):
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_storage_settings_export_csv_secret_free(client):
    ac, seed = client
    headers = await _admin(ac, seed)

    exported = await ac.get("/api/v1/settings/storage/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "backend" in header
    assert "media_dir" in header or "bucket" in header
    assert "access_key" not in header.lower()
    assert "secret" not in header.lower()
    assert "password" not in header.lower()
    assert "S3_ACCESS_KEY" not in text
    assert "S3_SECRET_KEY" not in text


@pytest.mark.asyncio
async def test_storage_settings_export_requires_admin(client):
    ac, seed = client
    cashier = await auth_headers(
        ac, email="cashier@alpha.example.com", tenant_slug="alpha"
    )
    denied = await ac.get("/api/v1/settings/storage/export", headers=cashier)
    assert denied.status_code in (401, 403), denied.text


def test_company_storage_export_ui_s1():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert "Stage 140" in page
    assert "/settings/storage/export" in page
    assert "Export storage settings CSV" in page
