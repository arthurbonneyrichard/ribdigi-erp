"""Stage 113 N1 — Read Notifications Shell leaf + page URL sync."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_read_notifications_leaf_n1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "status=read" in shell
    assert "Read Notifications" in shell
    assert "/notifications?status=read" in shell


def test_notifications_page_honors_read_status_n1():
    page = (ROOT / "frontend/app/notifications/page.tsx").read_text(encoding="utf-8")
    assert "syncUrl" in page
    assert "Stage 113" in page
    assert "status: 'read'" in page or 'status: "read"' in page or "setStatus('read')" in page
