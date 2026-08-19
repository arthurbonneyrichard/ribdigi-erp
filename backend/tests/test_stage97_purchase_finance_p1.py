"""Stage 97 P1 — Purchase & Finance discoverability."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_purchasing_settings_tab_and_outstanding_ui():
    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "'settings'" in purchasing or '"settings"' in purchasing
    assert "Purchase settings" in purchasing or "purchase-settings" in purchasing
    assert "outstanding" in purchasing
    assert "invoiceStatusFilter" in purchasing


def test_shell_and_anchors_p1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "Outstanding Purchases" in shell
    assert "status=outstanding" in shell
    assert "Purchase Settings" in shell
    assert "tab=settings" in shell
    assert "Opening Balances" in shell
    assert "#opening-balances" in shell
    assert "Fiscal Period" in shell
    assert "#fiscal-period" in shell
    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'id="opening-balances"' in accounting
    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'id="fiscal-period"' in company


def test_purchase_invoice_status_param_in_api():
    api = (ROOT / "backend/app/api.py").read_text(encoding="utf-8")
    assert "async def list_purchase_invoices" in api
    assert "outstanding" in api
    assert "PURCHASE_INVOICE_OPEN" in api


@pytest.mark.asyncio
async def test_purchase_invoice_outstanding_filter_api(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    bad = await ac.get("/api/v1/purchasing/invoices?status=bogus", headers=headers)
    assert bad.status_code == 400

    outstanding = await ac.get(
        "/api/v1/purchasing/invoices?status=outstanding", headers=headers
    )
    assert outstanding.status_code == 200, outstanding.text
    for row in outstanding.json().get("data") or []:
        assert row["status"] in {"unpaid", "partial", "overdue"}
