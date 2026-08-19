"""Stage 15 D1 — documentation fidelity for sales inventory–ledger chain."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage15_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_15_FIDELITY.md")
    assert "standard-cost COGS" in fidelity or "COGS `5000`" in fidelity or "Dr COGS" in fidelity
    assert "INSUFFICIENT_STOCK" in fidelity
    assert "sales_return_posted" in fidelity
    assert "invoice_posted" in fidelity
    assert "C1" in fidelity and "I1" in fidelity and "H1" in fidelity
    assert "R1" in fidelity and "T1" in fidelity and "A1" in fidelity
    assert "test_sales_inventory_ledger_chain_c1.py" in fidelity
    assert "test_sales_audit_a1.py" in fidelity
    assert "test_stage15_fidelity_d1.py" in fidelity

    plan = _read("docs/STAGE_15_PLAN.md")
    assert "| **D1**" in plan and "COMPLETE" in plan
    assert "STAGE_15_FIDELITY.md" in plan
    assert "| **C1**" in plan and "COMPLETE" in plan
    assert "| **A1**" in plan and "COMPLETE" in plan
    assert "| **H15x**" in plan and "COMPLETE" in plan
    assert "ADR-036" in plan or "STAGE_15_EXIT_CRITERIA.md" in plan
    assert "Closed" in plan or "exit met" in plan.lower() or "ADR-036" in plan


def test_stage15_api_and_security_docs():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 15 H1" in api
    assert "Stage 15 I1" in api
    assert "Stage 15 A1" in api
    assert "Stage 15 R1" in api or "Stage 15 R1/A1" in api
    assert "INSUFFICIENT_STOCK" in api
    assert "sales_return_posted" in api
    assert "COGS" in api and "5000" in api and "1200" in api

    security = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 15 A1" in security
    assert "invoice_posted" in security
    assert "sales_return_posted" in security


def test_stage15_br_manual_launch():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "Stage 15 H1" in br
    assert "Stage 15 I1" in br
    assert "Stage 15 A1" in br
    assert "Stage 15 R1" in br
    assert "Stage 15 T1" in br
    assert "Stage 15 C1" in br or "Stage 15 C1/H1" in br

    manual = _read("docs/USER_MANUAL.md")
    assert "Stage 15" in manual
    assert "COGS" in manual
    assert "STAGE_15_FIDELITY.md" in manual

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_sales_inventory_ledger_chain_c1.py" in launch
    assert "test_sales_cogs_inventory_i1.py" in launch
    assert "test_sales_invoice_atomicity_h1.py" in launch
    assert "test_sales_return_chain_r1.py" in launch
    assert "test_sales_tax_filing_t1.py" in launch
    assert "test_sales_audit_a1.py" in launch
    assert "test_stage15_fidelity_d1.py" in launch


def test_stage15_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_15_FIDELITY.md" in pr
    assert "test_sales_inventory_ledger_chain_c1.py" in pr
    assert "test_sales_cogs_inventory_i1.py" in pr or "COGS `5000`" in pr
    assert "test_sales_tax_filing_t1.py" in pr
    assert "sales_return_posted" in pr
    assert "invoice_posted" in pr
    assert "STAGE_15_EXIT_CRITERIA.md" in pr or "ADR-036" in pr

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_15_FIDELITY.md" in roadmap
    assert "Stage 15 D1" in roadmap
    assert "Stage 15 exit" in roadmap
    assert "ADR_036_STAGE15_FREEZE.md" in roadmap
    assert "ADR_035_STAGE15_OPEN.md" in roadmap
    assert "STAGE_16_PLAN.md" in roadmap or "ADR_037_STAGE16_OPEN.md" in roadmap
