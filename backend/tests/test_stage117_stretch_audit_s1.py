"""Stage 117 S1 — Stretch tenant Audit module Shell leaves."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_stretch_audit_leaves_s1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "module=notifications" in shell
    assert "module=backup" in shell
    assert "module=ai" in shell
    assert "module=reports" in shell
    assert "module=dashboard" in shell
    assert "Notifications Audit" in shell
    assert "Backup Audit" in shell
    assert "AI Audit" in shell
    assert "Reports Audit" in shell
    assert "Dashboard Audit" in shell


def test_audit_page_honors_stretch_modules_s1():
    page = (ROOT / "frontend/app/audit/page.tsx").read_text(encoding="utf-8")
    assert "Stage 117" in page
    assert "module" in page
