"""Stage 96 D1 — documentation fidelity for Tenant MVP Outline Surface Fidelity Ops."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage96_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_96_FIDELITY.md")
    assert "Outline" in fidelity or "Surface" in fidelity or "Dashboard" in fidelity
    for name in (
        "test_stage96_dashboard_overview_b1.py",
        "test_stage96_global_search_g1.py",
        "test_stage96_leaf_fidelity_l1.py",
        "test_stage96_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-198" in fidelity or "ADR_198" in fidelity
    assert "H96x" in fidelity
    plan = _read("docs/STAGE_96_PLAN.md")
    assert "STAGE_96_FIDELITY.md" in plan
    for ws in ("B1", "G1", "L1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws
    h96 = [ln for ln in plan.splitlines() if "| **H96x** |" in ln][0]
    assert "PENDING" in h96 or "COMPLETE" in h96
    assert any(x in plan for x in ("D1 next", "D1 complete", "H96x next", "Closed", "exit met"))


def test_stage96_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_96_FIDELITY.md" in br
    assert "Stage 96 D1" in br or "test_stage96_fidelity_d1.py" in br
    assert "Stage 96 B1" in br or "Stage 96 G1" in br or "Stage 96 L1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_96_FIDELITY.md" in fidelity_tail or "Stage 96 D1" in fidelity_tail


def test_stage96_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 96 D1" in api or "STAGE_96_FIDELITY.md" in api
    assert "test_stage96_fidelity_d1.py" in api or "STAGE_96_FIDELITY.md" in api
    assert "Stage 96 G1" in api or "/search" in api or "global search" in api.lower()
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 96 D1" in deploy or "STAGE_96_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 96 D1" in sec or "STAGE_96_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage96_dashboard_overview_b1.py" in launch
    assert "test_stage96_global_search_g1.py" in launch
    assert "test_stage96_leaf_fidelity_l1.py" in launch
    assert "test_stage96_fidelity_d1.py" in launch
    assert "STAGE_96_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert "Global Search" in manual or "/search" in manual


def test_stage96_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_96_FIDELITY.md" in pr and "test_stage96_fidelity_d1.py" in pr
    assert "Stage 96 D1" in pr and "Stage 96 B1" in pr and "Stage 96 G1" in pr and "Stage 96 L1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_96_FIDELITY.md" in roadmap and "Stage 96 D1" in roadmap
    assert "ADR_198_STAGE96_OPEN.md" in roadmap and "STAGE_96_PLAN.md" in roadmap
    assert "test_stage96_fidelity_d1.py" in roadmap
