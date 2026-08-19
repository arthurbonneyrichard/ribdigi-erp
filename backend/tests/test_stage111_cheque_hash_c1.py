"""Stage 111 C1 — Accounting #cheques hash + deposited/cleared leaves."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_cheque_hash_and_status_leaves_c1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/accounting?tab=cheques#cheques" in shell
    assert "cheque_status=pending#cheques" in shell
    assert "cheque_status=deposited#cheques" in shell
    assert "cheque_status=cleared#cheques" in shell
    assert "cheque_direction=received#cheques" in shell
    assert "cheque_direction=issued#cheques" in shell
    assert "Deposited Cheques" in shell
    assert "Cleared Cheques" in shell


def test_accounting_cheques_hash_honor_c1():
    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'id="cheques"' in accounting
    assert "hash === 'cheques'" in accounting or 'hash == "cheques"' in accounting
    assert "setTab('cheques')" in accounting or 'setTab("cheques")' in accounting
    assert "scrollIntoView" in accounting
    assert "Stage 111" in accounting
