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


def test_lifecycle_remainders_use_hover_classes():
    """Post GRN / Close books / Skip next / Post / Receive / Ship remainders."""
    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'className="btn-ok"' in purchasing
    assert "Post GRN (accept / reject)" in purchasing
    assert purchasing.index('className="btn-ok"') < purchasing.index("Post GRN (accept / reject)")
    assert "Receive all accepted" in purchasing
    assert 'className="btn-ok" onClick={() => postReturn(r.id)' in purchasing

    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'className="btn-danger" onClick={closeBooks}' in accounting
    assert 'className="btn-ok" onClick={reopenBooks}' in accounting

    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'className="btn-danger"' in expenses
    assert "Skip next" in expenses
    assert 'onClick={() => skipNextRecurring(r.id)' in expenses

    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'className="btn-ok" onClick={() => postInvoice(inv)' in sales
    assert 'Post credit' in sales and 'className="btn-ok"' in sales

    inventory = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "transferAct(t.id, 'ship')" in inventory
    assert "transferAct(t.id, 'receive')" in inventory
    assert inventory.count('className="btn-ok"') >= 3  # approve + ship + receive

    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert "act(t.id, 'ship')" in stores
    assert "act(t.id, 'receive')" in stores
    assert stores.count('className="btn-ok"') >= 3
