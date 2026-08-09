"""Stage 1 E15 — English-only MVP + i18n scaffold (ADR-006 / BR-2.7)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_me_exposes_english_locale_only(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    me = await ac.get("/api/v1/me", headers=headers)
    assert me.status_code == 200, me.text
    data = me.json()["data"]
    assert data["locale"] == "en"
    assert data["preferred_language"] == "en"
    assert data["supported_locales"] == ["en"]


@pytest.mark.asyncio
async def test_preferred_language_rejects_non_english(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    bad = await ac.patch(
        "/api/v1/me",
        headers=headers,
        json={"preferred_language": "fr"},
    )
    assert bad.status_code == 400, bad.text
    detail = bad.json().get("detail") or {}
    if isinstance(detail, dict):
        assert detail.get("code") == "LOCALE_UNSUPPORTED"
        assert detail.get("supported_locales") == ["en"]

    ok = await ac.patch(
        "/api/v1/me",
        headers=headers,
        json={"preferred_language": "en"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["preferred_language"] == "en"
    assert ok.json()["data"]["supported_locales"] == ["en"]


def test_adr_006_and_frontend_i18n_scaffold_exist():
    adr = (ROOT / "docs" / "ADR_006_LANGUAGE_I18N.md").read_text(encoding="utf-8")
    assert "English" in adr
    assert "i18n" in adr.lower()
    assert "post-MVP" in adr or "post-MVP" in adr.replace("post-mvp", "post-MVP")

    scaffold = (ROOT / "frontend" / "lib" / "i18n.ts").read_text(encoding="utf-8")
    assert "DEFAULT_LOCALE" in scaffold
    assert "SUPPORTED_LOCALES" in scaffold
    assert "function t(" in scaffold or "export function t" in scaffold
