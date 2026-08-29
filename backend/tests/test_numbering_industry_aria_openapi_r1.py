"""OpenAPI honesty tips #596–#601: numbering/industry aria-labels."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_numbering_industry_aria_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Sales document numbering prefix aria OpenAPI",
        "Purchasing document numbering prefix aria OpenAPI",
        "Expense number prefix aria OpenAPI",
        "Inventory document numbering prefix aria OpenAPI",
        "POS document numbering prefix aria OpenAPI",
        "Company / Platform industry aria OpenAPI",
    ):
        assert title in agents, title
    assert "Invoice number prefix" in agents
    assert "POS sale number prefix" in agents
    assert "Company industry" in agents

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Company industry" in docs
    assert "Tenant industry" in docs
    assert "POS (Sale/Shift)" in docs or "POS sale number prefix" in docs

    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    for label in (
        "Invoice number prefix",
        "Quotation number prefix",
        "Sales order number prefix",
        "Sales return number prefix",
        "Credit note number prefix",
        "Payment receipt number prefix",
        "Invoice next number",
    ):
        assert f'aria-label="{label}"' in sales, label

    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(
        encoding="utf-8"
    )
    for label in (
        "Purchase order number prefix",
        "GRN number prefix",
        "Purchase invoice number prefix",
        "Purchase request number prefix",
        "Purchase return number prefix",
        "Debit note number prefix",
        "Supplier payment number prefix",
    ):
        assert f'aria-label="{label}"' in purchasing, label

    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Expense number prefix"' in expenses
    assert 'aria-label="Expense next number"' in expenses

    inventory = (ROOT / "frontend/app/inventory/page.tsx").read_text(
        encoding="utf-8"
    )
    for label in (
        "Stock transfer number prefix",
        "Stock count number prefix",
        "Opening stock number prefix",
    ):
        assert f'aria-label="{label}"' in inventory, label

    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="POS sale number prefix"' in pos
    assert 'aria-label="POS session number prefix"' in pos

    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Company industry"' in company

    platform = (ROOT / "frontend/app/platform/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Tenant industry"' in platform
