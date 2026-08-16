"""Soft Activate/Deactivate use btn-ok / btn-danger on master-data pages."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_users_soft_activate_deactivate_colors():
    page = _read("frontend/app/users/page.tsx")
    assert 'className="btn-danger" onClick={() => setActive(r.id, false)' in page
    assert 'className="btn-ok" onClick={() => setActive(r.id, true)' in page
    assert 'className="btn-ok"' in page and "setCustomRoleActive" in page
    assert 'className="btn-danger"' in page and "setCustomRoleActive" in page


def test_inventory_product_and_catalog_soft_colors():
    page = _read("frontend/app/inventory/page.tsx")
    assert 'className="btn-ok" onClick={() => setProductActive(true)' in page
    assert 'className="btn-danger" onClick={() => setProductActive(false)' in page
    assert 'className="btn-ok" onClick={() => activateVariant(v.id)' in page
    assert 'className="btn-danger"' in page and "deactivateVariant" in page
    assert page.count('className="btn-danger"') >= 4
    assert page.count('className="btn-ok"') >= 4


def test_stores_org_soft_colors():
    page = _read("frontend/app/stores/page.tsx")
    assert 'className="btn-danger" onClick={() => setStoreActive(s.id, false)' in page
    assert 'className="btn-ok" onClick={() => setStoreActive(s.id, true)' in page
    assert "setWarehouseActive(w.id, false)" in page
    assert "setWarehouseActive(w.id, true)" in page
    assert page.count('className="btn-danger"') >= 4
    assert page.count('className="btn-ok"') >= 4
    assert "setBranchActive" in page and "btn-danger" in page
    assert "setDepartmentActive" in page and "btn-ok" in page


def test_accounting_coa_and_bank_soft_colors():
    page = _read("frontend/app/accounting/page.tsx")
    assert 'className="btn-ok" onClick={() => setAccountActive(r.id, true)' in page
    assert "setAccountActive(r.id, false)" in page and "btn-danger" in page
    assert "setConnectionActive" in page and "btn-ok" in page and "btn-danger" in page


def test_party_tax_expense_soft_toggle_colors():
    sales = _read("frontend/app/sales/page.tsx")
    assert "setCustomerActive" in sales and "btn-ok" in sales and "btn-danger" in sales
    assert "setGroupActive" in sales and "btn-ok" in sales

    purchasing = _read("frontend/app/purchasing/page.tsx")
    assert "setSupplierActive" in purchasing and "btn-ok" in purchasing and "btn-danger" in purchasing

    tax = _read("frontend/app/tax/page.tsx")
    assert 'className={r.is_active === false ? \'btn-ok\' : \'btn-danger\'}' in tax

    expenses = _read("frontend/app/expenses/page.tsx")
    assert 'className={c.is_active === false ? \'btn-ok\' : \'btn-danger\'}' in expenses


def test_platform_staff_soft_colors():
    page = _read("frontend/app/platform/staff/page.tsx")
    assert 'className="btn-ok"' in page and "setActive(u, true)" in page
    assert 'className="btn-danger"' in page and "setActive(u, false)" in page
