"""Stage 107 O1 — Ops leaves discoverability."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_platform_shell_tenant_ops_leaves_o1():
    shell = (ROOT / "frontend/components/PlatformShell.tsx").read_text(encoding="utf-8")
    assert "At-risk Tenants" in shell
    assert "focus=at-risk" in shell
    assert "New Tenants" in shell
    assert "created_this_month=true" in shell


def test_shell_backup_history_leaf_o1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/backup#history" in shell
    assert "Backup History" in shell


def test_backup_history_anchor_o1():
    backup = (ROOT / "frontend/app/backup/page.tsx").read_text(encoding="utf-8")
    assert 'id="history"' in backup
    assert "scrollIntoView" in backup
    assert "history" in backup
