"""OpenAPI honesty tips #874–#904: catalog/user name defense + bank recon money_json + report export aria."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.honesty import money_json, optional_honest_narrative, require_honest_narrative
from app import ai_reports as ai_reports_mod
from app import api as api_mod
from app import api_keys as api_keys_mod
from app import bank_recon as bank_recon_mod
from app import catalog as catalog_mod
from app import catalog_meta as catalog_meta_mod
from app import custom_roles as custom_roles_mod
from app import customer_groups as customer_groups_mod
from app import expenses as expenses_mod
from app import platform_staff as platform_staff_mod
from app import report_schedules as report_schedules_mod
from app import tax as tax_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch10_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Product name defense-in-depth OpenAPI",
        "Variant name defense-in-depth OpenAPI",
        "Variant attributes defense-in-depth OpenAPI",
        "Category name defense-in-depth OpenAPI",
        "Brand name defense-in-depth OpenAPI",
        "Unit name defense-in-depth OpenAPI",
        "Customer group name defense-in-depth OpenAPI",
        "Custom role label defense-in-depth OpenAPI",
        "Tax rate name defense-in-depth OpenAPI",
        "Expense category name defense-in-depth OpenAPI",
        "User full_name defense-in-depth OpenAPI",
        "Platform staff full_name defense-in-depth OpenAPI",
        "API key name defense-in-depth OpenAPI",
        "Report schedule name defense-in-depth OpenAPI",
        "AI report template name defense-in-depth OpenAPI",
        "Bank recon unmatched journal money_json Decimal pilot OpenAPI",
        "Report sales returns Excel aria OpenAPI",
        "Report sales returns CSV aria OpenAPI",
        "Report inventory valuation Excel aria OpenAPI",
        "Report inventory movements Excel aria OpenAPI",
        "Report inventory movements CSV aria OpenAPI",
        "Report inventory expiry Excel aria OpenAPI",
        "Report inventory expiry CSV aria OpenAPI",
        "Report inventory transfers Excel aria OpenAPI",
        "Report inventory transfers CSV aria OpenAPI",
        "Report inventory stock counts Excel aria OpenAPI",
        "Report inventory stock counts CSV aria OpenAPI",
        "Report purchases pending orders Excel aria OpenAPI",
        "Report purchases pending orders CSV aria OpenAPI",
        "Report purchases returns Excel aria OpenAPI",
        "Report purchases returns CSV aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2. Authentication")[0]
    assert "money_json" in standards
    assert "unmatched journal" in standards.lower()

    reports_page = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Export sales returns Excel"' in reports_page
    assert 'aria-label="Export sales returns CSV"' in reports_page
    assert 'aria-label="Export inventory valuation Excel"' in reports_page
    assert 'aria-label="Export inventory movements Excel"' in reports_page
    assert 'aria-label="Export inventory movements CSV"' in reports_page
    assert 'aria-label="Export inventory expiry Excel"' in reports_page
    assert 'aria-label="Export inventory expiry CSV"' in reports_page
    assert 'aria-label="Export inventory transfers Excel"' in reports_page
    assert 'aria-label="Export inventory transfers CSV"' in reports_page
    assert 'aria-label="Export inventory stock counts Excel"' in reports_page
    assert 'aria-label="Export inventory stock counts CSV"' in reports_page
    assert 'aria-label="Export purchases pending orders Excel"' in reports_page
    assert 'aria-label="Export purchases pending orders CSV"' in reports_page
    assert 'aria-label="Export purchases returns Excel"' in reports_page
    assert 'aria-label="Export purchases returns CSV"' in reports_page


def test_optional_helpers_and_money_json_batch10():
    assert require_honest_narrative("Widget Pack", label="product name") == "Widget Pack"
    with pytest.raises(HTTPException) as exc:
        require_honest_narrative("!!!", label="product name")
    assert exc.value.status_code == 400
    assert optional_honest_narrative(None, label="variant attribute") is None
    assert optional_honest_narrative("XL", label="variant attribute") == "XL"
    with pytest.raises(HTTPException):
        optional_honest_narrative("http://evil", label="variant attribute")
    assert money_json("3.25") == 3.25


def test_money_json_wired_batch10_bank_recon():
    src = inspect.getsource(bank_recon_mod.unmatched_book_lines)
    assert "money_json" in src
    assert "money_json(line.debit)" in src
    assert "money_json(line.credit)" in src
    assert "money_json(signed)" in src


def test_services_wire_honest_narrative_batch10():
    assert "require_honest_narrative" in inspect.getsource(catalog_mod.create_variant)
    assert "require_honest_narrative" in inspect.getsource(catalog_mod.update_variant)
    assert "optional_honest_narrative" in inspect.getsource(catalog_mod._clean_attr)
    assert "require_honest_narrative" in inspect.getsource(catalog_meta_mod.create_category)
    assert "require_honest_narrative" in inspect.getsource(catalog_meta_mod.update_category)
    assert "require_honest_narrative" in inspect.getsource(catalog_meta_mod.create_brand)
    assert "require_honest_narrative" in inspect.getsource(catalog_meta_mod.update_brand)
    assert "require_honest_narrative" in inspect.getsource(catalog_meta_mod.create_unit)
    assert "require_honest_narrative" in inspect.getsource(catalog_meta_mod.update_unit)
    assert "require_honest_narrative" in inspect.getsource(customer_groups_mod.create_group)
    assert "require_honest_narrative" in inspect.getsource(customer_groups_mod.update_group)
    assert "require_honest_narrative" in inspect.getsource(custom_roles_mod.create_custom_role)
    assert "require_honest_narrative" in inspect.getsource(custom_roles_mod.update_custom_role)
    assert "require_honest_narrative" in inspect.getsource(tax_mod.update_tax_rate)
    assert "require_honest_narrative" in inspect.getsource(expenses_mod.update_category)
    assert "require_honest_narrative" in inspect.getsource(api_keys_mod.create_key)
    assert "require_honest_narrative" in inspect.getsource(report_schedules_mod.create_schedule)
    assert "require_honest_narrative" in inspect.getsource(report_schedules_mod.update_schedule)
    assert "require_honest_narrative" in inspect.getsource(ai_reports_mod.create_template)
    assert "require_honest_narrative" in inspect.getsource(platform_staff_mod.create_platform_staff)
    assert "require_honest_narrative" in inspect.getsource(platform_staff_mod.update_platform_staff)
    assert "require_honest_narrative" in inspect.getsource(api_mod.add_product)
    assert "require_honest_narrative" in inspect.getsource(api_mod.patch_product)
    assert "require_honest_narrative" in inspect.getsource(api_mod.add_tax)
    assert "require_honest_narrative" in inspect.getsource(api_mod.create_expense_category)
    assert "require_honest_narrative" in inspect.getsource(api_mod.add_user)
    assert "require_honest_narrative" in inspect.getsource(api_mod.update_user)
    assert "require_honest_narrative" in inspect.getsource(api_mod.update_me)
