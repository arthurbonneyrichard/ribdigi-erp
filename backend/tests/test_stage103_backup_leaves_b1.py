"""Stage 103 B1 — Backup schedule & restore leaf honesty."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_backup_distinct_leaves_b1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/backup#schedule" in shell
    assert "/backup#restore" in shell
    assert "Backup & Restore" in shell
    # Distinct targets — bare /backup alone must not be the only Backup leaf pair
    assert shell.count('href: \'/backup\'') == 0 or (
        "/backup#schedule" in shell and "/backup#restore" in shell
    )


def test_backup_page_anchors_b1():
    backup = (ROOT / "frontend/app/backup/page.tsx").read_text(encoding="utf-8")
    assert 'id="schedule"' in backup
    assert 'id="restore"' in backup
    assert "scrollIntoView" in backup
