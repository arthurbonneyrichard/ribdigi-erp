"""Stage 143 O1 — onboarding checklist CSV export."""

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
async def test_onboarding_checklist_export_csv(client):
    ac, seed = client
    headers = await _super(ac, seed)

    exported = await ac.get("/api/v1/onboarding/checklist/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "step_id" in header and "title" in header and "progress_pct" in header
    assert "setup_company" in text
    assert "add_products" in text
    assert "first_sale" in text


def test_onboarding_checklist_export_ui_o1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "Stage 143" in shell
    assert "/onboarding/checklist/export" in shell
    assert "Export checklist CSV" in shell
