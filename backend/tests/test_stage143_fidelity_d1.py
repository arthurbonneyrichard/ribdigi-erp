"""Stage 143 D1 — documentation fidelity for company profile / jobs / onboarding CSV exports."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage143_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_143_FIDELITY.md")
    assert (
        "profile" in fidelity.lower()
        or "jobs" in fidelity.lower()
        or "onboarding" in fidelity.lower()
    )
    for name in (
        "test_stage143_company_profile_p1.py",
        "test_stage143_jobs_catalog_j1.py",
        "test_stage143_onboarding_checklist_o1.py",
        "test_stage143_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-292" in fidelity or "ADR_292" in fidelity
    assert "H143x" in fidelity
    plan = _read("docs/STAGE_143_PLAN.md")
    assert "STAGE_143_FIDELITY.md" in plan
    for ws in ("P1", "J1", "O1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage143_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_143_FIDELITY.md" in br
    assert "Stage 143 D1" in br or "test_stage143_fidelity_d1.py" in br
    assert "Stage 143 P1" in br or "Stage 143 J1" in br or "Stage 143 O1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_143_FIDELITY.md" in fidelity_tail or "Stage 143 D1" in fidelity_tail


def test_stage143_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 143 D1" in api or "STAGE_143_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 143 D1" in deploy or "STAGE_143_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 143 D1" in sec or "STAGE_143_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage143_company_profile_p1.py" in launch
    assert "test_stage143_jobs_catalog_j1.py" in launch
    assert "test_stage143_onboarding_checklist_o1.py" in launch
    assert "test_stage143_fidelity_d1.py" in launch
    assert "STAGE_143_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "tenants/me/export" in manual
        or "Profile" in manual
        or "jobs/export" in manual
        or "Jobs" in manual
        or "checklist/export" in manual
        or "Onboarding" in manual
        or "Checklist" in manual
    )


def test_stage143_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_143_FIDELITY.md" in pr and "test_stage143_fidelity_d1.py" in pr
    assert "Stage 143 D1" in pr and "Stage 143 P1" in pr and "Stage 143 J1" in pr and "Stage 143 O1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_143_FIDELITY.md" in roadmap and "Stage 143 D1" in roadmap
    assert "ADR_292_STAGE143_OPEN.md" in roadmap and "STAGE_143_PLAN.md" in roadmap
