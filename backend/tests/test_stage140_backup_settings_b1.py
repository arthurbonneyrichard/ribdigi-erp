"""Stage 140 B1 — backup settings CSV export."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _admin(ac, seed):
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_backup_settings_export_csv(client):
    ac, seed = client
    headers = await _admin(ac, seed)

    patched = await ac.patch(
        "/api/v1/backup/settings",
        headers=headers,
        json={
            "enabled": True,
            "frequency": "weekly",
            "retention_count": 14,
            "hour_utc": 3,
        },
    )
    assert patched.status_code == 200, patched.text

    exported = await ac.get("/api/v1/backup/settings/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "enabled" in header
    assert "frequency" in header
    assert "retention_count" in header
    assert "hour_utc" in header
    assert "weekly" in text
    assert "14" in text
    assert "secret" not in header.lower()
    assert "password" not in header.lower()
    assert "archive" not in header.lower()


def test_backup_settings_export_ui_b1():
    page = (ROOT / "frontend/app/backup/page.tsx").read_text(encoding="utf-8")
    assert "Stage 140" in page
    assert "/backup/settings/export" in page
    assert "Export backup settings CSV" in page
