"""Stage 145 D1 — documentation fidelity for AI security / templates / insights CSV exports."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage145_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_145_FIDELITY.md")
    assert (
        "security" in fidelity.lower()
        or "template" in fidelity.lower()
        or "insight" in fidelity.lower()
    )
    for name in (
        "test_stage145_security_alerts_s1.py",
        "test_stage145_report_templates_t1.py",
        "test_stage145_business_insights_i1.py",
        "test_stage145_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-296" in fidelity or "ADR_296" in fidelity
    assert "H145x" in fidelity
    plan = _read("docs/STAGE_145_PLAN.md")
    assert "STAGE_145_FIDELITY.md" in plan
    for ws in ("S1", "T1", "I1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage145_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_145_FIDELITY.md" in br
    assert "Stage 145 D1" in br or "test_stage145_fidelity_d1.py" in br
    assert "Stage 145 S1" in br or "Stage 145 T1" in br or "Stage 145 I1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_145_FIDELITY.md" in fidelity_tail or "Stage 145 D1" in fidelity_tail


def test_stage145_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 145 D1" in api or "STAGE_145_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 145 D1" in deploy or "STAGE_145_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 145 D1" in sec or "STAGE_145_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage145_security_alerts_s1.py" in launch
    assert "test_stage145_report_templates_t1.py" in launch
    assert "test_stage145_business_insights_i1.py" in launch
    assert "test_stage145_fidelity_d1.py" in launch
    assert "STAGE_145_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "security/alerts/export" in manual
        or "Security Alerts" in manual
        or "templates/export" in manual
        or "Templates" in manual
        or "insights/export" in manual
        or "Insights" in manual
    )


def test_stage145_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_145_FIDELITY.md" in pr and "test_stage145_fidelity_d1.py" in pr
    assert "Stage 145 D1" in pr and "Stage 145 S1" in pr and "Stage 145 T1" in pr and "Stage 145 I1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_145_FIDELITY.md" in roadmap and "Stage 145 D1" in roadmap
    assert "ADR_296_STAGE145_OPEN.md" in roadmap and "STAGE_145_PLAN.md" in roadmap
