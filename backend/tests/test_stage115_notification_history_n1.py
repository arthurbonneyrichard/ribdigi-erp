"""Stage 115 N1 — Notification History status=all honesty + Shell leaf."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_notification_history_leaf_n1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "status=all" in shell
    assert "Notification History" in shell
    assert "/notifications?status=all" in shell


def test_notifications_history_sentinel_honesty_n1():
    page = (ROOT / "frontend/app/notifications/page.tsx").read_text(encoding="utf-8")
    assert "Stage 115" in page
    assert "status=all" in page or "status: 'all'" in page or "setStatus('all')" in page
    assert "st !== 'all'" in page or 'st != "all"' in page or "st !== \"all\"" in page
    assert "setStatus('all')" in page
    assert "disabled={status === 'all'}" in page
