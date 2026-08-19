"""Stage 151 D1 — documentation fidelity for health / evidence / at-risk CSV exports."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage151_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_151_FIDELITY.md")
    assert (
        "health" in fidelity.lower()
        or "evidence" in fidelity.lower()
        or "at-risk" in fidelity.lower()
    )
    for name in (
        "test_stage151_platform_health_h1.py",
        "test_stage151_platform_evidence_e1.py",
        "test_stage151_at_risk_a1.py",
        "test_stage151_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-308" in fidelity or "ADR_308" in fidelity
    assert "H151x" in fidelity
    plan = _read("docs/STAGE_151_PLAN.md")
    assert "STAGE_151_FIDELITY.md" in plan
    for ws in ("H1", "E1", "A1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage151_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_151_FIDELITY.md" in br
    assert "Stage 151 D1" in br or "test_stage151_fidelity_d1.py" in br
    assert "Stage 151 H1" in br or "Stage 151 E1" in br or "Stage 151 A1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_151_FIDELITY.md" in fidelity_tail or "Stage 151 D1" in fidelity_tail


def test_stage151_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 151 D1" in api or "STAGE_151_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 151 D1" in deploy or "STAGE_151_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 151 D1" in sec or "STAGE_151_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage151_platform_health_h1.py" in launch
    assert "test_stage151_platform_evidence_e1.py" in launch
    assert "test_stage151_at_risk_a1.py" in launch
    assert "test_stage151_fidelity_d1.py" in launch
    assert "STAGE_151_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "health/export" in manual
        or "Health Checks" in manual
        or "evidence/export" in manual
        or "Operator Evidence" in manual
        or "at-risk/export" in manual
        or "At-Risk" in manual
    )


def test_stage151_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_151_FIDELITY.md" in pr and "test_stage151_fidelity_d1.py" in pr
    assert "Stage 151 D1" in pr and "Stage 151 H1" in pr and "Stage 151 E1" in pr and "Stage 151 A1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_151_FIDELITY.md" in roadmap and "Stage 151 D1" in roadmap
    assert "ADR_308_STAGE151_OPEN.md" in roadmap and "STAGE_151_PLAN.md" in roadmap
