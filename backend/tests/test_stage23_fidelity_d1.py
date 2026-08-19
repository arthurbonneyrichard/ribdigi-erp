"""Stage 23 D1 — documentation fidelity for reports dimension & MVP gates (BR-14)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage23_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_23_FIDELITY.md")
    assert "BR-14" in fidelity
    assert "test_financial_report_filters_f1.py" in fidelity
    assert "test_financial_comparative_c1.py" in fidelity
    assert "test_isolation_matrix_i1.py" in fidelity
    assert "test_mvp_gate_closure_g1.py" in fidelity
    assert "test_logical_dr_drill_b1.py" in fidelity
    assert "test_stage23_fidelity_d1.py" in fidelity
    assert "ADR-051" in fidelity or "ADR_051" in fidelity
    assert "compare=true" in fidelity
    assert "store_id" in fidelity and "branch_id" in fidelity
    assert "WAL" in fidelity or "PITR" in fidelity
    assert "H23x" in fidelity
    assert "ADR-052" in fidelity or "ADR_052" in fidelity or "exit met" in fidelity.lower()

    plan = _read("docs/STAGE_23_PLAN.md")
    assert "STAGE_23_FIDELITY.md" in plan
    for ws in ("F1", "C1", "I1", "G1", "B1", "D1", "H23x"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}**" in ln][0]
        assert "COMPLETE" in line, ws
    assert "ADR-051" in plan or "ADR_051" in plan
    assert "ADR-052" in plan or "ADR_052" in plan
    assert "Closed" in plan or "exit met" in plan.lower()


def test_stage23_br_14_and_dr_checkboxes_synced():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "Stage 23 F1" in br
    assert "Stage 23 C1" in br
    assert "Stage 23 B1" in br
    assert "Stage 23 D1" in br
    assert "STAGE_23_FIDELITY.md" in br

    s145 = br.split("#### BR-14.5 Financial Reports")[1].split("---")[0]
    assert "[x] **Profit & Loss Statement**" in s145
    assert "[x] **Cash Flow Statement**" in s145
    assert "[x] **Balance Sheet" in s145
    assert "[x] All reports filterable by date range, branch, store" in s145
    assert "store_id" in s145 and "branch_id" in s145
    assert "[x] Comparative reports" in s145
    assert "compare=true" in s145

    s163 = br.split("#### BR-16.3 Database Restore")[1].split("---")[0]
    assert "[x] Restore from backup archive" in s163
    assert "[x] Restore validation" in s163
    assert "[x] Logical DR drill automation evidence" in s163
    assert "test_logical_dr_drill_b1.py" in s163


def test_stage23_api_user_manual_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 23 D1" in api or "STAGE_23_FIDELITY.md" in api
    assert "test_stage23_fidelity_d1.py" in api or "STAGE_23_FIDELITY.md" in api
    assert "/reports/balance-sheet" in api
    assert "/reports/profit-loss" in api
    assert "/reports/cash-flow" in api
    assert "store_id" in api and "branch_id" in api
    assert "compare" in api
    assert "/backup" in api
    assert "confirm_text" in api and "RESTORE" in api

    manual = _read("docs/USER_MANUAL.md")
    assert "Stage 23" in manual or "STAGE_23_FIDELITY" in manual
    assert "STAGE_23_FIDELITY" in manual or "Stage 23 D1" in manual
    assert "branch" in manual.lower()
    assert "Compare" in manual or "compare" in manual
    assert "Balance Sheet" in manual
    assert "backup" in manual.lower() or "Backup" in manual
    assert "RESTORE" in manual or "restore" in manual.lower()

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_financial_report_filters_f1.py" in launch
    assert "test_financial_comparative_c1.py" in launch
    assert "test_isolation_matrix_i1.py" in launch
    assert "test_mvp_gate_closure_g1.py" in launch
    assert "test_logical_dr_drill_b1.py" in launch
    assert "test_stage23_fidelity_d1.py" in launch
    assert "STAGE_23_FIDELITY.md" in launch


def test_stage23_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_23_FIDELITY.md" in pr
    assert "test_stage23_fidelity_d1.py" in pr
    assert "Stage 23 D1" in pr
    assert "Stage 23 F1" in pr or "test_financial_report_filters_f1.py" in pr
    assert "Stage 23 C1" in pr or "test_financial_comparative_c1.py" in pr
    assert "Stage 23 B1" in pr or "test_logical_dr_drill_b1.py" in pr
    assert "- [x] Disaster recovery drill passes." in pr
    assert "- [x] Reports and exports complete." in pr

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_23_FIDELITY.md" in roadmap
    assert "Stage 23 D1" in roadmap
    assert "ADR_051_STAGE23_OPEN.md" in roadmap
    assert "STAGE_23_PLAN.md" in roadmap
