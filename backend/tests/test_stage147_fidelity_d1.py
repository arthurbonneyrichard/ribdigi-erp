"""Stage 147 D1 — documentation fidelity for sales / expense / purchases analysis CSV exports."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage147_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_147_FIDELITY.md")
    assert (
        "sales" in fidelity.lower()
        or "expense" in fidelity.lower()
        or "purchase" in fidelity.lower()
    )
    for name in (
        "test_stage147_sales_analysis_s1.py",
        "test_stage147_expense_analysis_e1.py",
        "test_stage147_purchases_analysis_p1.py",
        "test_stage147_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-300" in fidelity or "ADR_300" in fidelity
    assert "H147x" in fidelity
    plan = _read("docs/STAGE_147_PLAN.md")
    assert "STAGE_147_FIDELITY.md" in plan
    for ws in ("S1", "E1", "P1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage147_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_147_FIDELITY.md" in br
    assert "Stage 147 D1" in br or "test_stage147_fidelity_d1.py" in br
    assert "Stage 147 S1" in br or "Stage 147 E1" in br or "Stage 147 P1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_147_FIDELITY.md" in fidelity_tail or "Stage 147 D1" in fidelity_tail


def test_stage147_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 147 D1" in api or "STAGE_147_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 147 D1" in deploy or "STAGE_147_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 147 D1" in sec or "STAGE_147_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage147_sales_analysis_s1.py" in launch
    assert "test_stage147_expense_analysis_e1.py" in launch
    assert "test_stage147_purchases_analysis_p1.py" in launch
    assert "test_stage147_fidelity_d1.py" in launch
    assert "STAGE_147_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "sales/analysis/export" in manual
        or "Sales Analysis" in manual
        or "expenses/analysis/export" in manual
        or "Expense Analysis" in manual
        or "purchases/analysis/export" in manual
        or "Purchases Analysis" in manual
    )


def test_stage147_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_147_FIDELITY.md" in pr and "test_stage147_fidelity_d1.py" in pr
    assert "Stage 147 D1" in pr and "Stage 147 S1" in pr and "Stage 147 E1" in pr and "Stage 147 P1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_147_FIDELITY.md" in roadmap and "Stage 147 D1" in roadmap
    assert "ADR_300_STAGE147_OPEN.md" in roadmap and "STAGE_147_PLAN.md" in roadmap
