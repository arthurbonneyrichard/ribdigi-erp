"""Stage 114 O1 — Transfer scope, platform industry, users role, audit module leaves."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_ops_filter_leaves_o1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "transfers&scope=inter_store" in shell
    assert "transfers&scope=warehouse" in shell
    assert "Inter-store Transfer Reports" in shell
    assert "Warehouse Transfer Reports" in shell
    assert "role=cashier" in shell
    assert "role=company_admin" in shell
    assert "role=store_manager" in shell
    assert "role=accountant" in shell
    assert "Cashier Users" in shell
    assert "module=purchasing" in shell
    assert "module=inventory" in shell
    assert "module=accounting" in shell
    assert "module=expenses" in shell
    assert "Purchasing Audit" in shell
    assert "Inventory Audit" in shell


def test_platform_shell_industry_leaves_o1():
    shell = (ROOT / "frontend/components/PlatformShell.tsx").read_text(encoding="utf-8")
    assert "industry=retail" in shell
    assert "industry=pharmacy" in shell
    assert "industry=restaurant" in shell
    assert "industry=bakery" in shell
    assert "industry=wholesale" in shell
    assert "industry=manufacturing" in shell
    assert "industry=mart" in shell
    assert "Retail Tenants" in shell
    assert "Pharmacy Tenants" in shell


def test_pages_honor_ops_filters_o1():
    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert "Stage 114" in reports
    assert "inter_store" in reports and "warehouse" in reports
    users = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert "Stage 114" in users
    assert "role" in users
    audit = (ROOT / "frontend/app/audit/page.tsx").read_text(encoding="utf-8")
    assert "Stage 114" in audit
    tenants = (ROOT / "frontend/app/platform/tenants/page.tsx").read_text(encoding="utf-8")
    assert "Stage 114" in tenants
    assert "industry" in tenants
