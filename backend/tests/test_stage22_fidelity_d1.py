"""Stage 22 D1 — documentation fidelity for expenses/ledger/credit/tax (BR-9–12)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage22_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_22_FIDELITY.md")
    assert "BR-9" in fidelity and "BR-12" in fidelity
    assert "test_expense_categories_entry_e1.py" in fidelity
    assert "test_expense_approval_recurring_a1.py" in fidelity
    assert "test_coa_fidelity_c1.py" in fidelity
    assert "test_cash_bank_recon_b1.py" in fidelity
    assert "test_ar_ap_export_p1.py" in fidelity
    assert "test_customer_credit_r1.py" in fidelity
    assert "test_tax_config_fidelity_t1.py" in fidelity
    assert "test_stage22_fidelity_d1.py" in fidelity
    assert "ADR-049" in fidelity or "ADR_049" in fidelity
    assert "industry-agnostic" in fidelity.lower()
    assert "Open Banking" in fidelity
    assert "scan_payment_due" in fidelity
    assert "H22x" in fidelity

    plan = _read("docs/STAGE_22_PLAN.md")
    assert "STAGE_22_FIDELITY.md" in plan
    for ws in ("E1", "A1", "C1", "B1", "P1", "R1", "T1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}**" in ln][0]
        assert "COMPLETE" in line, ws
    h22 = [ln for ln in plan.splitlines() if "| **H22x**" in ln][0]
    assert "PENDING" in h22
    assert "ADR-049" in plan or "ADR_049" in plan


def test_stage22_br_9_to_12_checkboxes_synced():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "Stage 22 E1" in br
    assert "Stage 22 A1" in br
    assert "Stage 22 C1" in br
    assert "Stage 22 B1" in br
    assert "Stage 22 P1" in br
    assert "Stage 22 R1" in br
    assert "Stage 22 T1" in br
    assert "Stage 22 D1" in br
    assert "STAGE_22_FIDELITY.md" in br

    s91 = br.split("#### BR-9.1 Expense Categories")[1].split("#### BR-9.2")[0]
    assert "[x] Predefined categories" in s91
    assert "[x] Custom category creation" in s91
    assert "[x] Category-based budget allocation" in s91

    s93 = br.split("#### BR-9.3 Expense Approval")[1].split("#### BR-9.4")[0]
    assert "[x] Configurable approval thresholds" in s93
    assert "[x] Multi-level approval chain" in s93

    s95 = br.split("#### BR-9.5 Recurring Expenses")[1].split("---")[0]
    assert "[x] Set frequency (daily, weekly, monthly, yearly)" in s95
    assert "[x] Skip or modify individual occurrences" in s95

    s101 = br.split("#### BR-10.1 Chart of Accounts (COA)")[1].split("#### BR-10.2")[0]
    assert "[x] Predefined COA" in s101
    assert "[x] Opening balance entry" in s101
    assert "industry-agnostic" in s101.lower() or "Industry-agnostic" in s101

    s103 = br.split("#### BR-10.3 Cash & Bank Accounts")[1].split("#### BR-10.4")[0]
    assert "[x] Create cash accounts" in s103
    assert "[x] Bank reconciliation" in s103
    assert "[x] Cheque management" in s103

    s104 = br.split("#### BR-10.4 Accounts Receivable (AR)")[1].split("#### BR-10.5")[0]
    assert "[x] Auto-generation from sales invoices" in s104
    assert "[x] Customer aging report" in s104
    assert "[x] Partial payment support" in s104

    s105 = br.split("#### BR-10.5 Accounts Payable (AP)")[1].split("#### BR-10.6")[0]
    assert "[x] Auto-generation from purchase invoices" in s105
    assert "[x] Due date notifications" in s105

    s106 = br.split("#### BR-10.6 Financial Reports")[1].split("---")[0]
    assert "[x] Export to PDF and Excel" in s106

    s111 = br.split("#### BR-11.1 Customer Credit")[1].split("#### BR-11.2")[0]
    assert "[x] Set per-customer credit limit" in s111
    assert "[x] Block sales that exceed credit limit" in s111
    assert "[x] Customer statement generation" in s111
    assert "Stage 14 R1" in s111

    s121 = br.split("#### BR-12.1 Tax Configuration")[1].split("#### BR-12.2")[0]
    assert "[x] Add tax types" in s121
    assert "[x] Set tax applicability (inclusive/exclusive pricing)" in s121
    assert "[x] Compound tax" in s121


def test_stage22_api_user_manual_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 22 D1" in api or "STAGE_22_FIDELITY.md" in api
    assert "/expenses/categories" in api
    assert "/expenses/settings" in api or "expense approval" in api.lower()
    assert "/expenses/recurring" in api
    assert "/accounting/accounts" in api
    assert "/accounting/liquid-accounts" in api or "liquid-accounts" in api
    assert "/accounting/bank-statements" in api or "bank-statements" in api
    assert "/credit/aging" in api
    assert "/credit/customers/" in api and "statement" in api
    assert "/tax/rates" in api
    assert "/tax/calculate" in api or "tax/calculate" in api
    assert "/reports/export" in api
    assert "test_stage22_fidelity_d1.py" in api or "STAGE_22_FIDELITY.md" in api

    manual = _read("docs/USER_MANUAL.md")
    assert "Stage 22" in manual or "STAGE_22_FIDELITY" in manual
    assert "Expense" in manual
    assert "Chart of Accounts" in manual or "COA" in manual
    assert "Bank Reconciliation" in manual or "Reconcile" in manual
    assert "Credit Limit" in manual or "credit limit" in manual
    assert "Tax-Inclusive" in manual or "tax-inclusive" in manual.lower()
    assert "Compound" in manual or "compound" in manual.lower()

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_expense_categories_entry_e1.py" in launch
    assert "test_expense_approval_recurring_a1.py" in launch
    assert "test_coa_fidelity_c1.py" in launch
    assert "test_cash_bank_recon_b1.py" in launch
    assert "test_ar_ap_export_p1.py" in launch
    assert "test_customer_credit_r1.py" in launch
    assert "test_tax_config_fidelity_t1.py" in launch
    assert "test_stage22_fidelity_d1.py" in launch
    assert "STAGE_22_FIDELITY.md" in launch


def test_stage22_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_22_FIDELITY.md" in pr
    assert "test_stage22_fidelity_d1.py" in pr
    assert "Stage 22 D1" in pr
    assert "test_expense_categories_entry_e1.py" in pr or "Stage 22 E1" in pr
    assert "test_ar_ap_export_p1.py" in pr or "Stage 22 P1" in pr
    assert "test_tax_config_fidelity_t1.py" in pr or "Stage 22 T1" in pr

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_22_FIDELITY.md" in roadmap
    assert "Stage 22 D1" in roadmap
    assert "ADR_049_STAGE22_OPEN.md" in roadmap
    assert "STAGE_22_PLAN.md" in roadmap
