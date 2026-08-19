"""Stage 106 N1 — Notification inbox leaves."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_notification_inbox_leaves_n1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/notifications?status=unread" in shell
    assert "/notifications?group=stock" in shell
    assert "/notifications?group=orders" in shell
    assert "/notifications?group=payments" in shell
    assert "/notifications?group=system" in shell
    assert "Unread Notifications" in shell
    assert "Stock Alerts" in shell
    assert "Order Alerts" in shell
    assert "Payment Alerts" in shell
    assert "System Alerts" in shell


def test_notifications_page_url_sync_still_present_n1():
    page = (ROOT / "frontend/app/notifications/page.tsx").read_text(encoding="utf-8")
    assert "syncUrl" in page
    assert "status" in page and "group" in page
