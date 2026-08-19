"""Stage 109 O1 — Platform status leaves + bank-recon hash."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_platform_shell_tenant_status_leaves_o1():
    shell = (ROOT / "frontend/components/PlatformShell.tsx").read_text(encoding="utf-8")
    assert "status=active" in shell
    assert "status=trial" in shell
    assert "status=grace" in shell
    assert "status=suspended" in shell
    assert "Active Tenants" in shell
    assert "Trial Tenants" in shell
    assert "Grace Tenants" in shell
    assert "Suspended Tenants" in shell


def test_shell_bank_reconciliation_hash_o1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/accounting?tab=reconcile#bank-reconciliation" in shell
    assert "Bank Reconciliation" in shell


def test_accounting_bank_reconciliation_hash_honor_o1():
    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'id="bank-reconciliation"' in accounting
    assert "bank-reconciliation" in accounting
    assert "setTab('reconcile')" in accounting or 'setTab("reconcile")' in accounting
    assert "scrollIntoView" in accounting
