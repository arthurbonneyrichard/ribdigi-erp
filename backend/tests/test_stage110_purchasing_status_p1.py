"""Stage 110 P1 — Purchasing document status Shell leaves."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_purchasing_status_leaves_p1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "grn_status=draft" in shell
    assert "grn_status=posted" in shell
    assert "return_status=draft" in shell
    assert "return_status=posted" in shell
    assert "tab=invoices&status=draft" in shell
    assert "tab=invoices&status=overdue" in shell
    assert "Draft GRN" in shell
    assert "Posted GRN" in shell
    assert "Draft Purchase Returns" in shell
    assert "Draft Purchases" in shell
    assert "Overdue Purchases" in shell


def test_purchasing_page_status_url_params_p1():
    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "return_status" in purchasing
    assert "grn_status" in purchasing
    assert "writeQueryParam" in purchasing
    assert "Stage 110" in purchasing
