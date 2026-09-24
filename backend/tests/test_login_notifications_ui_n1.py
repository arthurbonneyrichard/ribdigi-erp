"""Notification list must not depend on settings Promise.all."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_notifications_page_loads_list_without_settings():
    page = (ROOT / "frontend/app/(dashboard)/notifications/page.tsx").read_text(encoding="utf-8")
    assert "Promise.all" not in page or "notifications/settings" not in page.split("Promise.all")[0]
    assert "api('/notifications/settings')" in page
    assert "setRows(notes.data" in page


def test_login_logo_is_preloaded():
    layout = (ROOT / "frontend/app/layout.tsx").read_text(encoding="utf-8")
    assert "/brand/logo-full.png" in layout
    assert "preload" in layout
    logo = (ROOT / "frontend/components/LoginBrandLogo.tsx").read_text(encoding="utf-8")
    assert "fetchPriority" in logo
    api = (ROOT / "frontend/lib/api.ts").read_text(encoding="utf-8")
    assert "location.replace" in api
