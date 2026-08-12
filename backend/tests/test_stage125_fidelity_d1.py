"""Stage 125 D1 — documentation fidelity for Inactive Liquid, Recurring & Export."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage125_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_125_FIDELITY.md")
    assert "Inactive" in fidelity or "Liquid" in fidelity or "Recurring" in fidelity
    for name in (
        "test_stage125_inactive_liquid_accounts_l1.py",
        "test_stage125_inactive_recurring_expenses_r1.py",
        "test_stage125_liquid_recurring_export_x1.py",
        "test_stage125_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-256" in fidelity or "ADR_256" in fidelity
    assert "H125x" in fidelity
    plan = _read("docs/STAGE_125_PLAN.md")
    assert "STAGE_125_FIDELITY.md" in plan
    for ws in ("L1", "R1", "X1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage125_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_125_FIDELITY.md" in br
    assert "Stage 125 D1" in br or "test_stage125_fidelity_d1.py" in br
    assert "Stage 125 L1" in br or "Stage 125 R1" in br or "Stage 125 X1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_125_FIDELITY.md" in fidelity_tail or "Stage 125 D1" in fidelity_tail


def test_stage125_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 125 D1" in api or "STAGE_125_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 125 D1" in deploy or "STAGE_125_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 125 D1" in sec or "STAGE_125_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage125_inactive_liquid_accounts_l1.py" in launch
    assert "test_stage125_inactive_recurring_expenses_r1.py" in launch
    assert "test_stage125_liquid_recurring_export_x1.py" in launch
    assert "test_stage125_fidelity_d1.py" in launch
    assert "STAGE_125_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "Inactive Liquid Accounts" in manual
        or "Paused Recurring" in manual
        or "liquid-accounts/export" in manual
        or "recurring/export" in manual
    )


def test_stage125_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_125_FIDELITY.md" in pr and "test_stage125_fidelity_d1.py" in pr
    assert "Stage 125 D1" in pr and "Stage 125 L1" in pr and "Stage 125 R1" in pr and "Stage 125 X1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_125_FIDELITY.md" in roadmap and "Stage 125 D1" in roadmap
    assert "ADR_256_STAGE125_OPEN.md" in roadmap and "STAGE_125_PLAN.md" in roadmap
