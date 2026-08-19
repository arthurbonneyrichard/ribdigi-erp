"""Stage 105 A1 — Platform audit filter URL sync."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_platform_shell_delivery_audit_leaf_a1():
    shell = (ROOT / "frontend/components/PlatformShell.tsx").read_text(encoding="utf-8")
    assert "/platform/audit?delivery_only=true" in shell
    assert "Delivery Audit" in shell


def test_platform_audit_url_sync_a1():
    page = (ROOT / "frontend/app/platform/audit/page.tsx").read_text(encoding="utf-8")
    assert "syncUrl" in page
    assert "delivery_only" in page
    assert "from_date" in page
    assert "window.history.replaceState" in page or "replaceState" in page
