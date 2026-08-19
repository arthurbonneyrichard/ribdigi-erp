"""Stage 139 D1 — documentation fidelity for budgets / account-tx / fiscal CSV exports."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage139_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_139_FIDELITY.md")
    assert (
        "budget" in fidelity.lower()
        or "transaction" in fidelity.lower()
        or "fiscal" in fidelity.lower()
    )
    for name in (
        "test_stage139_budgets_export_b1.py",
        "test_stage139_account_tx_export_a1.py",
        "test_stage139_fiscal_period_f1.py",
        "test_stage139_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-284" in fidelity or "ADR_284" in fidelity
    assert "H139x" in fidelity
    plan = _read("docs/STAGE_139_PLAN.md")
    assert "STAGE_139_FIDELITY.md" in plan
    for ws in ("B1", "A1", "F1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage139_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_139_FIDELITY.md" in br
    assert "Stage 139 D1" in br or "test_stage139_fidelity_d1.py" in br
    assert "Stage 139 B1" in br or "Stage 139 A1" in br or "Stage 139 F1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_139_FIDELITY.md" in fidelity_tail or "Stage 139 D1" in fidelity_tail


def test_stage139_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 139 D1" in api or "STAGE_139_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 139 D1" in deploy or "STAGE_139_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 139 D1" in sec or "STAGE_139_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage139_budgets_export_b1.py" in launch
    assert "test_stage139_account_tx_export_a1.py" in launch
    assert "test_stage139_fiscal_period_f1.py" in launch
    assert "test_stage139_fidelity_d1.py" in launch
    assert "STAGE_139_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "budgets/export" in manual
        or "Budget" in manual
        or "transactions/export" in manual
        or "ledger" in manual.lower()
        or "fiscal-period/export" in manual
        or "Fiscal" in manual
    )


def test_stage139_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_139_FIDELITY.md" in pr and "test_stage139_fidelity_d1.py" in pr
    assert "Stage 139 D1" in pr and "Stage 139 B1" in pr and "Stage 139 A1" in pr and "Stage 139 F1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_139_FIDELITY.md" in roadmap and "Stage 139 D1" in roadmap
    assert "ADR_284_STAGE139_OPEN.md" in roadmap and "STAGE_139_PLAN.md" in roadmap
