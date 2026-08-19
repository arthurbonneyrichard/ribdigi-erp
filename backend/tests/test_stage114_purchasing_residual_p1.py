"""Stage 114 P1 — Residual purchasing PR/PO + Paid Purchases Shell leaves."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_purchasing_residual_leaves_p1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "pr_status=draft" in shell
    assert "pr_status=approved" in shell
    assert "pr_status=rejected" in shell
    assert "pr_status=cancelled" in shell
    assert "pr_status=converted" in shell
    assert "Draft PRs" in shell
    assert "Approved PRs" in shell
    assert "Converted PRs" in shell
    assert "po_status=draft" in shell
    assert "po_status=sent" in shell
    assert "po_status=partially_received" in shell
    assert "po_status=received" in shell
    assert "po_status=cancelled" in shell
    assert "Partially Received POs" in shell
    assert "Paid Purchases" in shell
    assert "/purchasing?tab=invoices&status=paid" in shell


def test_purchasing_page_honors_residual_statuses_p1():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "Stage 114" in page
    assert "prAllowed" in page or "pr_status" in page
    assert "partially_received" in page
    assert "converted" in page
    assert "paid" in page
