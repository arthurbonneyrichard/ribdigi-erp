"""Stage 104 I1 — Commerce products / purchase invoices / sales status leaves."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_commerce_leaves_i1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/inventory?tab=products" in shell
    assert "Products" in shell
    assert "/purchasing?tab=invoices" in shell
    assert "Purchase Invoices" in shell
    assert "/sales?tab=invoices&status=draft" in shell
    assert "/sales?tab=invoices&status=overdue" in shell
    assert "Draft Invoices" in shell
    assert "Overdue Invoices" in shell
