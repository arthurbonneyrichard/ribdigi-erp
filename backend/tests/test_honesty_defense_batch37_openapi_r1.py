"""OpenAPI honesty tips #1884–#1894: residual money_json."""

from __future__ import annotations

from pathlib import Path

from app.honesty import money_json

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch37_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Purchase suggestion gap money_json Decimal pilot OpenAPI",
        "Purchase suggestion warehouse gap money_json Decimal pilot OpenAPI",
        "Purchase suggestion product max return money_json Decimal pilot OpenAPI",
        "Purchase suggestion product floor return money_json Decimal pilot OpenAPI",
        "Purchase suggestion product zero return money_json Decimal pilot OpenAPI",
        "Inventory warehouse suggested_order_qty gap money_json Decimal pilot OpenAPI",
        "Expense create amount money_json Decimal pilot OpenAPI",
        "Expense update amount money_json Decimal pilot OpenAPI",
        "Recurring expense create amount money_json Decimal pilot OpenAPI",
        "Recurring expense update amount money_json Decimal pilot OpenAPI",
        "GRN schema inferred rejected_qty money_json Decimal pilot OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2.")[0]
    assert "purchase-suggestion gap/warehouse gap/product returns" in standards
    assert "expense/recurring create+update amount" in standards
    assert "GRN schema inferred rejected_qty" in standards
    assert "money_json(round(...))" in standards


def test_money_json_wired_batch37():
    assert money_json("12.50") == 12.5

    suggestions = (ROOT / "backend/app/purchase_suggestions.py").read_text(
        encoding="utf-8"
    )
    assert (
        "money_json(round(money_json(reorder_level) - money_json(stock_qty), 3))"
        in suggestions
    )
    assert "money_json(max(rq, gap))" in suggestions
    assert "money_json(max(1.0, gap))" in suggestions
    assert suggestions.count("else money_json(0)") >= 2
    assert "money_json(stock.reorder_level or 0)" in suggestions
    assert "qty = money_json(" in suggestions
    assert "round(" in suggestions
    # warehouse gap: money_json(round(...)) nested under max
    assert "money_json(\n                                round(" in suggestions

    inventory = (ROOT / "backend/app/inventory.py").read_text(encoding="utf-8")
    assert (
        "money_json(max(reorder_qty, money_json(round(reorder - qty, 3))))"
        in inventory
    )

    expenses = (ROOT / "backend/app/expenses.py").read_text(encoding="utf-8")
    assert "amount=money_json(round(money_json(amount), 2))" in expenses
    assert "new_amount = money_json(round(money_json(amount), 2))" in expenses
    assert "row.amount = money_json(round(money_json(amount), 2))" in expenses

    schemas = (ROOT / "backend/app/schemas.py").read_text(encoding="utf-8")
    assert (
        "rejected = money_json(round(received - money_json(accepted), 6))"
        in schemas
    )


def test_no_bare_residual_round_money_assigns_batch37():
    """Last known bare round(...) money assigns should now be wrapped."""
    bare = []
    for rel in (
        "backend/app/expenses.py",
        "backend/app/schemas.py",
        "backend/app/inventory.py",
        "backend/app/purchase_suggestions.py",
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        # Collapse money_json(\n  round( for multi-line wraps
        import re

        collapsed = re.sub(r"money_json\(\s*\n\s*", "money_json(", text)
        for i, line in enumerate(collapsed.splitlines(), 1):
            if "round(" not in line or "money_json" in line:
                continue
            if line.strip().startswith("#"):
                continue
            # round nested inside money_json(max(..., round(...))) after collapse
            # should already have money_json on same line
            bare.append(f"{rel}:{i}:{line.strip()}")
    assert bare == [], bare
