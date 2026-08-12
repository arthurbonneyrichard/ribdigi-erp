"""Stage 152 D1 — documentation fidelity for dashboard / industries / permissions matrix CSV exports."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage152_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_152_FIDELITY.md")
    assert (
        "dashboard" in fidelity.lower()
        or "industr" in fidelity.lower()
        or "permission" in fidelity.lower()
    )
    for name in (
        "test_stage152_platform_dashboard_g1.py",
        "test_stage152_platform_industries_i1.py",
        "test_stage152_permissions_matrix_m1.py",
        "test_stage152_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-310" in fidelity or "ADR_310" in fidelity
    assert "H152x" in fidelity
    plan = _read("docs/STAGE_152_PLAN.md")
    assert "STAGE_152_FIDELITY.md" in plan
    for ws in ("G1", "I1", "M1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage152_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_152_FIDELITY.md" in br
    assert "Stage 152 D1" in br or "test_stage152_fidelity_d1.py" in br
    assert "Stage 152 G1" in br or "Stage 152 I1" in br or "Stage 152 M1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_152_FIDELITY.md" in fidelity_tail or "Stage 152 D1" in fidelity_tail


def test_stage152_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 152 D1" in api or "STAGE_152_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 152 D1" in deploy or "STAGE_152_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 152 D1" in sec or "STAGE_152_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage152_platform_dashboard_g1.py" in launch
    assert "test_stage152_platform_industries_i1.py" in launch
    assert "test_stage152_permissions_matrix_m1.py" in launch
    assert "test_stage152_fidelity_d1.py" in launch
    assert "STAGE_152_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "dashboard/export" in manual
        or "Dashboard Aggregates" in manual
        or "industries/export" in manual
        or "Industries Catalog" in manual
        or "permissions/export" in manual
        or "Permissions Matrix" in manual
    )


def test_stage152_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_152_FIDELITY.md" in pr and "test_stage152_fidelity_d1.py" in pr
    assert "Stage 152 D1" in pr and "Stage 152 G1" in pr and "Stage 152 I1" in pr and "Stage 152 M1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_152_FIDELITY.md" in roadmap and "Stage 152 D1" in roadmap
    assert "ADR_310_STAGE152_OPEN.md" in roadmap and "STAGE_152_PLAN.md" in roadmap
