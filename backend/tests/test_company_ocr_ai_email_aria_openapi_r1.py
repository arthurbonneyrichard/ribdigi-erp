"""OpenAPI honesty tips #590–#595: company/OCR/AI trim + email aria-labels."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_company_ocr_ai_email_aria_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Company company_name FE trim OpenAPI",
        "Expense OCR Apply FE trim OpenAPI",
        "AI create-expense OCR fields FE trim OpenAPI",
        "AI create-PI OCR fields FE trim OpenAPI",
        "Supplier email aria-label OpenAPI",
        "User email aria-label OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "String(tenant.company_name || '').trim()" in docs
    assert "Expense OCR payee" in docs
    assert "Supplier email" in docs
    assert "User email" in docs
    assert "Create draft expense trims extract" in docs
    assert "Create draft purchase invoice trims extract" in docs

    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert "company_name: String(tenant.company_name || '').trim()" in company

    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Expense OCR payee"' in expenses
    assert 'aria-label="Expense OCR description"' in expenses
    assert 'aria-label="Expense OCR reference"' in expenses
    assert "const payee = String(ocrDraft.payee || '').trim();" in expenses
    assert "if (payee) body.payee = payee;" in expenses

    ai = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert "payee: String(ex.payee || '').trim() || null" in ai
    assert "reference: String(ex.reference || '').trim() || null" in ai
    assert "supplier_invoice_number: String(ex.reference || '').trim() || null" in ai
    assert "notes: String(ex.description || '').trim() || null" in ai

    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(
        encoding="utf-8"
    )
    assert 'aria-label="Supplier email"' in purchasing
    assert "email: supplierEmail.trim() || null" in purchasing

    users = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="User email"' in users
