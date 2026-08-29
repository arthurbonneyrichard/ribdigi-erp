"""OpenAPI honesty tips #850–#873: company/org/party name defense + expense OCR money_json + report export aria."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.honesty import money_json, optional_honest_narrative, require_honest_narrative
from app import api as api_mod
from app import cash_transfers as cash_transfers_mod
from app import expense_ocr as expense_ocr_mod
from app import org_units as org_units_mod
from app import stores as stores_mod
from app import tenants as tenants_mod
from app import warehouses as warehouses_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch9_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Company company_name defense-in-depth OpenAPI",
        "Company legal_name defense-in-depth OpenAPI",
        "Company contact_person defense-in-depth OpenAPI",
        "Company address defense-in-depth OpenAPI",
        "Company billing_address defense-in-depth OpenAPI",
        "Company shipping_address defense-in-depth OpenAPI",
        "Company registration_number defense-in-depth OpenAPI",
        "Company tax_registration_number defense-in-depth OpenAPI",
        "Store name defense-in-depth OpenAPI",
        "Warehouse name defense-in-depth OpenAPI",
        "Branch name defense-in-depth OpenAPI",
        "Department name defense-in-depth OpenAPI",
        "Account name defense-in-depth OpenAPI",
        "Account bank_name defense-in-depth OpenAPI",
        "Account bank_branch defense-in-depth OpenAPI",
        "Party name defense-in-depth OpenAPI",
        "Expense OCR amount money_json Decimal pilot OpenAPI",
        "Report sales daily CSV aria OpenAPI",
        "Report salespeople Excel aria OpenAPI",
        "Report trial balance Excel aria OpenAPI",
        "Report trial balance CSV aria OpenAPI",
        "Report P&L PDF aria OpenAPI",
        "Report sales customers Excel aria OpenAPI",
        "Report sales by store Excel aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2. Authentication")[0]
    assert "money_json" in standards
    assert "expense OCR" in standards.lower() or "OCR suggestion" in standards

    reports_page = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Export sales daily CSV"' in reports_page
    assert 'aria-label="Export salespeople Excel"' in reports_page
    assert 'aria-label="Export trial balance Excel"' in reports_page
    assert 'aria-label="Export trial balance CSV"' in reports_page
    assert 'aria-label="Export P&L PDF"' in reports_page
    assert 'aria-label="Export sales customers Excel"' in reports_page
    assert 'aria-label="Export sales by store Excel"' in reports_page


def test_optional_helpers_and_money_json_batch9():
    assert require_honest_narrative("Acme Retail", label="company name", min_length=2) == "Acme Retail"
    with pytest.raises(HTTPException) as exc:
        require_honest_narrative("!!!", label="company name", min_length=2)
    assert exc.value.status_code == 400
    assert optional_honest_narrative(None, label="billing address") is None
    assert optional_honest_narrative("12 High St", label="billing address") == "12 High St"
    with pytest.raises(HTTPException):
        optional_honest_narrative("http://evil", label="billing address")
    assert money_json("12.50") == 12.5


def test_services_wire_honest_narrative_batch9():
    assert "require_honest_narrative" in inspect.getsource(tenants_mod.update_profile)
    assert "optional_honest_narrative" in inspect.getsource(tenants_mod.update_profile)
    assert "require_honest_narrative" in inspect.getsource(stores_mod.create_store)
    assert "require_honest_narrative" in inspect.getsource(stores_mod.update_store)
    assert "require_honest_narrative" in inspect.getsource(warehouses_mod.create_warehouse)
    assert "require_honest_narrative" in inspect.getsource(warehouses_mod.update_warehouse)
    assert "require_honest_narrative" in inspect.getsource(org_units_mod.create_branch)
    assert "require_honest_narrative" in inspect.getsource(org_units_mod.update_branch)
    assert "require_honest_narrative" in inspect.getsource(org_units_mod.create_department)
    assert "require_honest_narrative" in inspect.getsource(org_units_mod.update_department)
    assert "require_honest_narrative" in inspect.getsource(cash_transfers_mod.create_account)
    assert "require_honest_narrative" in inspect.getsource(cash_transfers_mod.update_account)
    assert "optional_honest_narrative" in inspect.getsource(cash_transfers_mod.create_account)
    assert "optional_honest_narrative" in inspect.getsource(cash_transfers_mod.update_account)
    assert "require_honest_narrative" in inspect.getsource(api_mod._normalize_party_profile)


def test_money_json_wired_batch9_expense_ocr():
    assert "money_json" in inspect.getsource(expense_ocr_mod.parse_receipt_text)
    parsed = expense_ocr_mod.parse_receipt_text("TOTAL: GHS 42.50\nPayee: Acme Supplies")
    assert parsed["fields"]["amount"] == 42.5
    assert isinstance(parsed["fields"]["amount"], float)
