"""Sidebar company brand space + /me company fields."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_sidebar_brand_ui_wired():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert 'className="brand"' in shell
    assert "brand-logo" in shell
    assert "brand-name" in shell
    assert "company_name" in shell
    assert "has_logo" in shell
    assert "/tenants/me/logo" in shell
    assert "topbar-brand" not in shell
    css = (ROOT / "frontend/app/globals.css").read_text(encoding="utf-8")
    assert ".brand{" in css or ".brand{" in css.replace(" ", "")
    assert "min-height:72px" in css
    assert "brand-name" in css
    assert "topbar-brand" not in css
    assert "width:min(120px,42%)" in css


@pytest.mark.asyncio
async def test_me_includes_company_brand_fields(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    me = await ac.get("/api/v1/me", headers=headers)
    assert me.status_code == 200, me.text
    data = me.json()["data"]
    assert "company_name" in data
    assert data["company_name"]
    assert "has_logo" in data
    assert isinstance(data["has_logo"], bool)
