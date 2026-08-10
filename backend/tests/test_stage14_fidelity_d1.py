"""Stage 14 D1 — documentation fidelity for finance closeout chain."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage14_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_14_FIDELITY.md")
    assert "expense_categories.account_id" in fidelity
    assert "as_of_date" in fidelity
    assert "expense_submitted" in fidelity
    assert "PATCH /tax/rates/{id}" in fidelity or "PATCH /tax/rates" in fidelity
    assert "E1" in fidelity and "A3" in fidelity and "R1" in fidelity
    assert "test_expense_coa_chain_e1.py" in fidelity
    assert "test_expense_audit_a3.py" in fidelity
    assert "test_stage14_fidelity_d1.py" in fidelity

    plan = _read("docs/STAGE_14_PLAN.md")
    assert "| **D1**" in plan and "COMPLETE" in plan
    assert "STAGE_14_FIDELITY.md" in plan
    assert "| **E1**" in plan and "COMPLETE" in plan
    assert "| **A3**" in plan and "COMPLETE" in plan
    assert "| **H14x**" in plan and "PENDING" in plan


def test_stage14_api_and_database_docs():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 14 E1" in api
    assert "Stage 14 E2" in api
    assert "Stage 14 A1" in api
    assert "Stage 14 A2" in api
    assert "Stage 14 T1" in api
    assert "Stage 14 R1" in api
    assert "Stage 14 A3" in api
    assert "expense_submitted" in api
    assert "as_of_date" in api
    assert "PATCH /tax/rates/{rate_id}" in api or "PATCH /tax/rates/{id}" in api

    db = _read("docs/DATABASE_DOCUMENTATION.md")
    assert "Stage 14 E1" in db
    assert "Stage 14 E2" in db
    assert "Stage 14 A1" in db
    assert "account_id UUID REFERENCES accounts(id)" in db
    assert "store_id UUID REFERENCES stores(id)" in db


def test_stage14_br_security_manual_launch():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "Stage 14 E1" in br
    assert "Stage 14 E2" in br
    assert "Stage 14 A1" in br
    assert "Stage 14 A2" in br
    assert "Stage 14 R1" in br
    assert "Stage 14 T1" in br

    security = _read("docs/SECURITY_GUIDE.md")
    assert "expense_submitted" in security
    assert "expense_rejected" in security
    assert "Stage 14 A3" in security

    manual = _read("docs/USER_MANUAL.md")
    assert "Stage 14 E1" in manual
    assert "Stage 14 A2" in manual
    assert "Stage 14 R1" in manual
    assert "Stage 14 T1" in manual
    assert "expense_submitted" in manual

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_expense_coa_chain_e1.py" in launch
    assert "test_journal_store_dimension_a1.py" in launch
    assert "test_expense_audit_a3.py" in launch


def test_stage14_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_14_FIDELITY.md" in pr
    assert "Stage 14 E1" in pr
    assert "Stage 14 A1" in pr
    assert "Stage 14 A2" in pr
    assert "Stage 14 T1" in pr
    assert "Stage 14 R1" in pr
    assert "Stage 14 A3" in pr

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_14_FIDELITY.md" in roadmap
    assert "Stage 14 D1" in roadmap
