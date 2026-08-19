"""Stage 142 D1 — documentation fidelity for POS sales / Z-report / drawer CSV exports."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage142_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_142_FIDELITY.md")
    assert (
        "sales" in fidelity.lower()
        or "z-report" in fidelity.lower()
        or "drawer" in fidelity.lower()
    )
    for name in (
        "test_stage142_pos_sales_s1.py",
        "test_stage142_z_report_z1.py",
        "test_stage142_drawer_settings_c1.py",
        "test_stage142_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-290" in fidelity or "ADR_290" in fidelity
    assert "H142x" in fidelity
    plan = _read("docs/STAGE_142_PLAN.md")
    assert "STAGE_142_FIDELITY.md" in plan
    for ws in ("S1", "Z1", "C1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage142_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_142_FIDELITY.md" in br
    assert "Stage 142 D1" in br or "test_stage142_fidelity_d1.py" in br
    assert "Stage 142 S1" in br or "Stage 142 Z1" in br or "Stage 142 C1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_142_FIDELITY.md" in fidelity_tail or "Stage 142 D1" in fidelity_tail


def test_stage142_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 142 D1" in api or "STAGE_142_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 142 D1" in deploy or "STAGE_142_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 142 D1" in sec or "STAGE_142_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage142_pos_sales_s1.py" in launch
    assert "test_stage142_z_report_z1.py" in launch
    assert "test_stage142_drawer_settings_c1.py" in launch
    assert "test_stage142_fidelity_d1.py" in launch
    assert "STAGE_142_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "pos/sales/export" in manual
        or "Sales Register" in manual
        or "Z-Report" in manual
        or "Z-report" in manual
        or "drawer-settings/export" in manual
        or "Drawer" in manual
    )


def test_stage142_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_142_FIDELITY.md" in pr and "test_stage142_fidelity_d1.py" in pr
    assert "Stage 142 D1" in pr and "Stage 142 S1" in pr and "Stage 142 Z1" in pr and "Stage 142 C1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_142_FIDELITY.md" in roadmap and "Stage 142 D1" in roadmap
    assert "ADR_290_STAGE142_OPEN.md" in roadmap and "STAGE_142_PLAN.md" in roadmap
