"""Stage 112 D1 — documentation fidelity for Report Schedule Leaves, Stores Cash Drawer & Platform Plan Ops."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage112_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_112_FIDELITY.md")
    assert "Schedule" in fidelity or "Cash Drawer" in fidelity or "Plan" in fidelity
    for name in (
        "test_stage112_report_schedules_r1.py",
        "test_stage112_stores_cash_drawer_s1.py",
        "test_stage112_platform_plan_p1.py",
        "test_stage112_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-230" in fidelity or "ADR_230" in fidelity
    assert "H112x" in fidelity
    plan = _read("docs/STAGE_112_PLAN.md")
    assert "STAGE_112_FIDELITY.md" in plan
    for ws in ("R1", "S1", "P1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage112_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_112_FIDELITY.md" in br
    assert "Stage 112 D1" in br or "test_stage112_fidelity_d1.py" in br
    assert "Stage 112 R1" in br or "Stage 112 S1" in br or "Stage 112 P1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_112_FIDELITY.md" in fidelity_tail or "Stage 112 D1" in fidelity_tail


def test_stage112_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 112 D1" in api or "STAGE_112_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 112 D1" in deploy or "STAGE_112_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 112 D1" in sec or "STAGE_112_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage112_report_schedules_r1.py" in launch
    assert "test_stage112_stores_cash_drawer_s1.py" in launch
    assert "test_stage112_platform_plan_p1.py" in launch
    assert "test_stage112_fidelity_d1.py" in launch
    assert "STAGE_112_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "Daily Report Schedules" in manual
        or "Cash Drawer" in manual
        or "Starter Plan Tenants" in manual
        or "Enabled Report Schedules" in manual
    )


def test_stage112_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_112_FIDELITY.md" in pr and "test_stage112_fidelity_d1.py" in pr
    assert "Stage 112 D1" in pr and "Stage 112 R1" in pr and "Stage 112 S1" in pr and "Stage 112 P1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_112_FIDELITY.md" in roadmap and "Stage 112 D1" in roadmap
    assert "ADR_230_STAGE112_OPEN.md" in roadmap and "STAGE_112_PLAN.md" in roadmap
