"""OpenAPI honesty tips #1745–#1778: residual money_json + FE aria."""

from __future__ import annotations

import inspect
from pathlib import Path

from app.honesty import money_json
from app import product_import as product_import_mod
from app import receipts as receipts_mod
from app import reports as reports_mod
from app import backup as backup_mod
from app import fx as fx_mod
from app import ai_inventory as ai_inventory_mod
from app import api as api_mod
from app import schemas as schemas_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch33_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Product CSV export cost_price money_json Decimal pilot OpenAPI",
        "Product CSV export selling_price money_json Decimal pilot OpenAPI",
        "Product CSV export stock_qty money_json Decimal pilot OpenAPI",
        "Product CSV export reorder_level money_json Decimal pilot OpenAPI",
        "Product CSV export dimensions money_json Decimal pilot OpenAPI",
        "Product CSV commit stock_qty money_json Decimal pilot OpenAPI",
        "Product CSV commit cost/selling money_json Decimal pilot OpenAPI",
        "Receipts _money money_json Decimal pilot OpenAPI",
        "Reports monthly sales inv money_json Decimal pilot OpenAPI",
        "Reports monthly sales pos money_json Decimal pilot OpenAPI",
        "Reports budget-vs-actual sort money_json Decimal pilot OpenAPI",
        "Backup JSON Decimal money_json Decimal pilot OpenAPI",
        "Backup proof values equal money_json Decimal pilot OpenAPI",
        "GRN schema received_qty money_json Decimal pilot OpenAPI",
        "GRN schema rejected/accepted money_json Decimal pilot OpenAPI",
        "FX quotes quote money_json Decimal pilot OpenAPI",
        "API product create dimensions money_json Decimal pilot OpenAPI",
        "API product update cost/selling/reorder money_json Decimal pilot OpenAPI",
        "API product update dimensions money_json Decimal pilot OpenAPI",
        "API product audit _jsonable money_json Decimal pilot OpenAPI",
        "AI inventory sold_90 money_json Decimal pilot OpenAPI",
        "Bank statement line amount validator money_json Decimal pilot OpenAPI",
        "Multi-Store Branch email aria OpenAPI",
        "Purchasing GRN received qty aria OpenAPI",
        "Accounting Attach journal file aria OpenAPI",
        "Accounting Bank statement import file aria OpenAPI",
        "AI Analyze document file aria OpenAPI",
        "Company logo file aria OpenAPI",
        "Expenses Upload attachment file aria OpenAPI",
        "Inventory Product gallery image file aria OpenAPI",
        "Inventory Product CSV import file aria OpenAPI",
        "Inventory Brand logo file aria OpenAPI",
        "Purchasing Upload invoice attachment file aria OpenAPI",
        "Users CSV import file aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2.")[0]
    assert "Product CSV export/commit" in standards
    assert "receipts `_money`" in standards or "receipts _money" in standards

    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Branch email"' in stores

    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "GRN received qty ${i.id}" in purchasing
    assert "Upload purchase invoice attachment ${inv.id}" in purchasing

    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "Attach journal file ${j.id}" in accounting
    assert 'aria-label="Bank statement import file"' in accounting

    ai = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="AI analyze document file"' in ai

    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Company logo file"' in company

    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert "Upload expense attachment ${r.id}" in expenses

    inventory = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Product gallery image file"' in inventory
    assert 'aria-label="Product CSV import file"' in inventory
    assert "Brand logo file ${b.id}" in inventory

    users = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="User CSV import file"' in users


def test_money_json_wired_batch33():
    assert money_json("12.50") == 12.5

    pi_src = Path(product_import_mod.__file__).read_text(encoding="utf-8")
    assert "def _csv_money" in pi_src
    assert '"cost_price": _csv_money(p.cost_price, places=4)' in pi_src
    assert '"selling_price": _csv_money(p.selling_price, places=4)' in pi_src
    assert '"stock_qty": _csv_money(p.stock_qty, places=3)' in pi_src
    assert '"reorder_level": _csv_money(p.reorder_level, places=3)' in pi_src
    assert "_csv_dim(getattr(p, \"weight\", None))" in pi_src
    assert "stock_qty = money_json(data.get(\"stock_qty\") or 0)" in pi_src
    assert "cost_price=money_json(data.get(\"cost_price\") or 0)" in pi_src
    assert "selling_price=money_json(data.get(\"selling_price\") or 0)" in pi_src

    money_src = inspect.getsource(receipts_mod._money)
    assert "money_json(value or 0)" in money_src

    reports_src = Path(reports_mod.__file__).read_text(encoding="utf-8")
    assert "inv = money_json((await db.execute(inv_stmt)).scalar() or 0)" in reports_src
    assert "pos = money_json((await db.execute(pos_stmt)).scalar() or 0)" in reports_src
    assert '(-money_json(r["actual"])' in reports_src

    backup_src = Path(backup_mod.__file__).read_text(encoding="utf-8")
    assert "return money_json(value)" in backup_src
    assert "money_json(expected or 0) == money_json(actual or 0)" in backup_src

    quotes_src = inspect.getsource(fx_mod.quotes_to_rate_to_base)
    assert "q = money_json(quotes.get(code) or 0)" in quotes_src

    ai_src = Path(ai_inventory_mod.__file__).read_text(encoding="utf-8")
    assert "money_json(sold_90.get(pid, 0)) <= 0" in ai_src

    api_src = Path(api_mod.__file__).read_text(encoding="utf-8")
    assert 'data[dim] = money_json(data[dim])' in api_src
    assert 'setattr(product, key, money_json(value))' in api_src
    assert "setattr(product, key, money_json(value) if value is not None else None)" in api_src
    assert "return money_json(value)" in api_src

    grn_src = inspect.getsource(schemas_mod.GrnItemCreate.require_reason_when_rejected)
    assert "received = money_json(self.received_qty or 0)" in grn_src
    assert "rejected = money_json(self.rejected_qty or 0)" in grn_src
    assert "money_json(accepted)" in grn_src

    amt_src = inspect.getsource(schemas_mod.BankStatementLineCreate._nonzero_amount)
    assert "amount = money_json(value)" in amt_src
