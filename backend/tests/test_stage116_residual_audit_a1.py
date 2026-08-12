"""Stage 116 A1 — Residual Audit module Shell leaves."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_residual_audit_leaves_a1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "module=credit" in shell
    assert "module=pos" in shell
    assert "module=tax" in shell
    assert "module=users" in shell
    assert "module=company" in shell
    assert "module=stores" in shell
    assert "module=security" in shell
    assert "Credit Audit" in shell
    assert "POS Audit" in shell
    assert "Tax Audit" in shell
    assert "Users Audit" in shell
    assert "Company Audit" in shell
    assert "Stores Audit" in shell
    assert "Security Audit" in shell


def test_audit_page_honors_module_param_a1():
    page = (ROOT / "frontend/app/audit/page.tsx").read_text(encoding="utf-8")
    assert "Stage 116" in page
    assert "module" in page
