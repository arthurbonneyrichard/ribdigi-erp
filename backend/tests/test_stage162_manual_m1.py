"""Stage 162 M1 — USER_MANUAL + Stage 95 shell IA amendment."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_user_manual_approved_parents_m1():
    manual = (ROOT / "docs/USER_MANUAL.md").read_text(encoding="utf-8")
    assert "Stage 162" in manual
    assert "Finance & Accounts" in manual
    assert "Inventory" in manual and "Stock" in manual
    assert "User Management" in manual
    assert "expand" in manual.lower() or "▾" in manual or "▸" in manual


def test_stage95_shell_test_amended_for_stage162():
    t = (ROOT / "backend/tests/test_stage95_shell_ia_n1.py").read_text(encoding="utf-8")
    assert "Stage 162" in t
    assert "Finance & Accounts" in t
    assert "Commerce" not in t or "supersedes" in t.lower()
