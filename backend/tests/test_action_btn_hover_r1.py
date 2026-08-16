"""Action button hover color classes (btn-ok / btn-danger)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_action_btn_hover_css_present():
    css = (ROOT / "frontend/app/globals.css").read_text(encoding="utf-8")
    assert "button.btn-ok" in css
    assert "button.btn-danger" in css
    assert "#dcfce7" in css or "#bbf7d0" in css  # green hover
    assert "#fee2e2" in css or "#fecaca" in css  # red hover
    assert '[data-theme="dark"] .main button.btn-ok' in css
    assert '[data-theme="dark"] .main button.btn-danger' in css


def test_sales_accept_reject_use_hover_classes():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'className="btn-ok"' in sales
    assert 'className="btn-danger"' in sales
    assert "accept" in sales and "btn-ok" in sales
    assert "/reject" in sales
    # Accept uses green, Reject uses red
    assert 'className="btn-ok" onClick={() => act(`/sales/quotations/${q.id}/accept`' in sales
    assert 'className="btn-danger" onClick={() => act(`/sales/quotations/${q.id}/reject`' in sales


def test_expenses_approve_reject_use_hover_classes():
    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'className="btn-ok" onClick={() => approve(r.id)' in expenses
    assert 'className="btn-danger" onClick={() => reject(r.id)' in expenses
