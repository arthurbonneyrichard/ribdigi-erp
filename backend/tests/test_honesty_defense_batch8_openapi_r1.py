"""OpenAPI honesty tips #831–#849: address/contact/supplier-invoice defense + tax filing/suggestions/AI-doc money_json + tax export aria."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.honesty import money_json, optional_honest_narrative, require_honest_narrative
from app import ai_documents as ai_documents_mod
from app import org_units as org_units_mod
from app import party_contacts as party_contacts_mod
from app import purchase_ocr as purchase_ocr_mod
from app import purchase_suggestions as purchase_suggestions_mod
from app import purchasing as purchasing_mod
from app import sales_docs as sales_docs_mod
from app import stores as stores_mod
from app import tax as tax_mod
from app import warehouses as warehouses_mod
from app.tax_filings import gh_vat as gh_vat_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch8_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "PO delivery_address defense-in-depth OpenAPI",
        "SO delivery_address defense-in-depth OpenAPI",
        "Party contact name defense-in-depth OpenAPI",
        "Party contact designation defense-in-depth OpenAPI",
        "Supplier invoice number defense-in-depth OpenAPI",
        "Store address defense-in-depth OpenAPI",
        "Warehouse address defense-in-depth OpenAPI",
        "Branch address defense-in-depth OpenAPI",
        "Tax filing pack money_json Decimal pilot OpenAPI",
        "Tax filing GH VAT money_json Decimal pilot OpenAPI",
        "Low-stock suggestions money_json Decimal pilot OpenAPI",
        "AI document PO match money_json Decimal pilot OpenAPI",
        "AI document create draft money_json Decimal pilot OpenAPI",
        "Tax filing export CSV aria OpenAPI",
        "Tax filing export Excel aria OpenAPI",
        "Tax filing export PDF aria OpenAPI",
        "Tax Ghana VAT export Excel aria OpenAPI",
        "Tax Ghana VAT export CSV aria OpenAPI",
        "Tax Ghana VAT export PDF aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2. Authentication")[0]
    assert "money_json" in standards
    assert "filing pack" in standards.lower() or "GH VAT" in standards
    assert "low-stock purchase suggestions" in standards.lower() or "suggestions" in standards.lower()

    tax_page = (ROOT / "frontend/app/tax/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Export tax filing CSV"' in tax_page
    assert 'aria-label="Export tax filing Excel"' in tax_page
    assert 'aria-label="Export tax filing PDF"' in tax_page
    assert 'aria-label="Export Ghana VAT Excel"' in tax_page
    assert 'aria-label="Export Ghana VAT CSV"' in tax_page
    assert 'aria-label="Export Ghana VAT PDF"' in tax_page


def test_optional_helpers_and_money_json_batch8():
    assert optional_honest_narrative(None, label="store address") is None
    assert optional_honest_narrative("12 High St", label="store address") == "12 High St"
    with pytest.raises(HTTPException) as exc:
        optional_honest_narrative("!!!", label="store address")
    assert exc.value.status_code == 400
    assert require_honest_narrative("Ada Contact", label="party contact name") == "Ada Contact"
    with pytest.raises(HTTPException):
        require_honest_narrative("!!!", label="party contact name")
    assert money_json("7.25") == 7.25


def test_services_wire_optional_honest_narrative_batch8():
    assert "optional_honest_narrative" in inspect.getsource(purchasing_mod.create_purchase_order)
    assert "optional_honest_narrative" in inspect.getsource(purchasing_mod.amend_purchase_order)
    assert "optional_honest_narrative" in inspect.getsource(purchasing_mod.create_purchase_invoice)
    assert "optional_honest_narrative" in inspect.getsource(sales_docs_mod.create_order)
    assert "optional_honest_narrative" in inspect.getsource(sales_docs_mod.confirm_order)
    assert "require_honest_narrative" in inspect.getsource(party_contacts_mod.create_contact)
    assert "optional_honest_narrative" in inspect.getsource(party_contacts_mod.create_contact)
    assert "require_honest_narrative" in inspect.getsource(party_contacts_mod.update_contact)
    assert "optional_honest_narrative" in inspect.getsource(
        purchase_ocr_mod.update_purchase_invoice_draft
    )
    assert "optional_honest_narrative" in inspect.getsource(stores_mod.create_store)
    assert "optional_honest_narrative" in inspect.getsource(stores_mod.update_store)
    assert "optional_honest_narrative" in inspect.getsource(warehouses_mod.create_warehouse)
    assert "optional_honest_narrative" in inspect.getsource(warehouses_mod.update_warehouse)
    assert "optional_honest_narrative" in inspect.getsource(org_units_mod.create_branch)
    assert "optional_honest_narrative" in inspect.getsource(org_units_mod.update_branch)
    assert "optional_honest_narrative" in inspect.getsource(
        ai_documents_mod.create_purchase_invoice_from_extract
    )


def test_money_json_wired_batch8_serializers():
    assert "money_json" in inspect.getsource(tax_mod.tax_filing_pack)
    assert "money_json" in inspect.getsource(gh_vat_mod.map_return)
    assert "money_json" in inspect.getsource(purchase_suggestions_mod.list_low_stock_suggestions)
    assert "money_json" in inspect.getsource(ai_documents_mod.match_purchase_orders)
    assert "money_json" in inspect.getsource(ai_documents_mod.create_expense_from_extract)
    assert "money_json" in inspect.getsource(ai_documents_mod.create_purchase_invoice_from_extract)
