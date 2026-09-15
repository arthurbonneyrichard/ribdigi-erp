"""OpenAPI honesty tips #650–#667: free-text defense-in-depth + money_json + residual aria."""

from __future__ import annotations

import inspect
import math
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.honesty import money_json, require_honest_narrative
from app import accounting as accounting_mod
from app import cheques as cheques_mod
from app import expenses as expenses_mod
from app import product_import as product_import_mod
from app import tenants as tenants_mod
from app import api as api_mod
from app.sales import serialize_invoice

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_defense_money_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Expense reject reason defense-in-depth OpenAPI",
        "Recurring skip reason defense-in-depth OpenAPI",
        "Journal unpost reason defense-in-depth OpenAPI",
        "Tenant suspend reason defense-in-depth OpenAPI",
        "Sales invoice money_json Decimal pilot OpenAPI",
        "Tenant company name aria OpenAPI",
        "Tenant currency aria OpenAPI",
        "Tenant admin email aria OpenAPI",
        "Subscription term length aria OpenAPI",
        "Store entitlement override aria OpenAPI",
        "Backup retention hour aria OpenAPI",
        "POS split tender aria OpenAPI",
        "Period close/reopen reason defense-in-depth OpenAPI",
        "Cheque bounce/cancel reason defense-in-depth OpenAPI",
        "Product CSV import free-text honesty OpenAPI",
        "Company SMTP port aria OpenAPI",
        "Stock quantity aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2. Authentication")[0]
    assert "money_json" in standards
    assert "Decimal" in standards

    platform = (ROOT / "frontend/app/platform/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Tenant company name"' in platform
    assert 'aria-label="Tenant currency"' in platform
    assert 'aria-label="Tenant admin email"' in platform
    assert 'aria-label="Subscription term length"' in platform
    assert 'aria-label="Store entitlement override"' in platform
    assert 'aria-label="Store entitlement override draft"' in platform

    backup = (ROOT / "frontend/app/backup/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Backup retention count"' in backup
    assert 'aria-label="Backup hour UTC"' in backup

    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="POS cash tender"' in pos
    assert 'aria-label="POS card tender"' in pos

    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Company SMTP port"' in company

    inventory = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Stock-in quantity"' in inventory
    assert 'aria-label="Opening stock quantity"' in inventory
    assert 'aria-label="Stock adjustment quantity"' in inventory
    assert 'aria-label="Stock-out quantity"' in inventory


def test_require_honest_narrative_rejects_garbage():
    assert require_honest_narrative("Over limit A1", label="reason") == "Over limit A1"
    with pytest.raises(HTTPException) as blank:
        require_honest_narrative("   ", label="rejection reason")
    assert blank.value.status_code == 400
    assert "required" in blank.value.detail
    for bad in ("!!!", "http://evil", "@@@@"):
        with pytest.raises(HTTPException) as exc:
            require_honest_narrative(bad, label="rejection reason")
        assert exc.value.status_code == 400
        assert "plain narrative" in exc.value.detail


def test_money_json_decimal_to_finite_float():
    assert money_json(None) == 0.0
    assert money_json(Decimal("199.99")) == 199.99
    assert isinstance(money_json(Decimal("10.50")), float)
    assert math.isfinite(money_json(Decimal("10.50")))
    with pytest.raises(ValueError):
        money_json(float("nan"))
    with pytest.raises(ValueError):
        money_json(float("inf"))
    with pytest.raises(TypeError):
        money_json(True)


def test_services_wire_require_honest_narrative():
    assert "require_honest_narrative" in inspect.getsource(expenses_mod.reject_expense)
    assert "require_honest_narrative" in inspect.getsource(expenses_mod.skip_next_recurring)
    assert "require_honest_narrative" in inspect.getsource(accounting_mod.unpost_journal_entry)
    assert "require_honest_narrative" in inspect.getsource(accounting_mod.close_books)
    assert "require_honest_narrative" in inspect.getsource(accounting_mod.reopen_books)
    assert "require_honest_narrative" in inspect.getsource(cheques_mod.bounce_cheque)
    assert "require_honest_narrative" in inspect.getsource(cheques_mod.cancel_cheque)
    assert "require_honest_narrative" in inspect.getsource(tenants_mod.suspend_tenant)
    api_src = Path(api_mod.__file__).read_text(encoding="utf-8")
    assert api_src.count("require_honest_narrative(payload.reason") >= 2


def test_product_import_validates_name_sku_description_honesty():
    src = inspect.getsource(product_import_mod.validate_import_rows)
    assert "ProductNameValue" in src
    assert "ProductSkuValue" in src
    assert "ProductDescriptionValue" in src
    assert "TypeAdapter" in src


def test_serialize_invoice_uses_money_json():
    src = inspect.getsource(serialize_invoice)
    assert "money_json" in src
    assert "float(invoice.subtotal)" not in src
    assert "float(invoice.total_amount)" not in src
