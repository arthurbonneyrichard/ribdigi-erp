"""Stage 232 S1 — Shell Accounts Receivable / Accounts Payable leaves."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_accounts_receivable_payable_s1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "Accounts Receivable" in shell
    assert "/accounting/receivables" in shell
    assert "Accounts Payable" in shell
    assert "/accounting/payables" in shell
    # Stage 98 O1 retained
    assert "Outstanding Receivables" in shell
    assert "/credit?kind=receivable" in shell
    assert "Outstanding Payables" in shell
    assert "/credit?kind=payable" in shell


def test_ar_ap_surface_register_s1():
    data = json.loads((ROOT / "ops/mvp/ar-ap-accounting-surface.json").read_text(encoding="utf-8"))
    assert data["stage"] == 232
    assert data["packaging_complete"] is True
    assert data["new_ar_ap_engine_claimed"] is False
    assert data["go_live_claimed"] is False
    assert data["open_banking_claimed"] is False
    assert data["distinct_from_stage22_ar_ap_engine"] is True
    assert data["distinct_from_stage98_o1_outstanding_leaves"] is True
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel
