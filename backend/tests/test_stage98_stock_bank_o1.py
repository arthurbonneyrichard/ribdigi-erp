"""Stage 98 O1 — Stock ops & bank surface discoverability."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_shell_stock_bank_credit_links():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "Stock Counts" in shell
    assert "/inventory?tab=counts" in shell
    assert "Warehouse Transfers" in shell
    assert "/inventory?tab=transfers" in shell
    assert "Bank Reconciliation" in shell
    assert "/accounting?tab=reconcile" in shell
    assert "Cheques" in shell
    assert "/accounting?tab=cheques" in shell
    assert "Outstanding Receivables" in shell
    assert "/credit?kind=receivable" in shell
    assert "Outstanding Payables" in shell
    assert "/credit?kind=payable" in shell


def test_credit_kind_url_sync_and_accounting_anchors():
    credit = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert "setKindAndUrl" in credit
    assert "kind" in credit
    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'id="bank-reconciliation"' in accounting
    assert 'id="cheques"' in accounting


@pytest.mark.asyncio
async def test_dashboard_credit_kpi_kind_links(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/dashboard", headers=headers)
    assert r.status_code == 200, r.text
    links = r.json()["data"].get("kpi_links") or {}
    assert links.get("ar_total_due") == "/credit?kind=receivable"
    assert links.get("ap_total_due") == "/credit?kind=payable"
    assert links.get("credit_outstanding") == "/credit?kind=receivable"
