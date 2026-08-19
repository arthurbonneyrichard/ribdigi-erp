"""Stage 162 D1 — documentation fidelity for approved navigation hierarchy."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage162_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_162_FIDELITY.md")
    assert "navigation" in fidelity.lower() or "Shell" in fidelity
    for name in (
        "test_stage162_nav_n1.py",
        "test_stage162_stock_parents_s1.py",
        "test_stage162_manual_m1.py",
        "test_stage162_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-330" in fidelity or "ADR_330" in fidelity
    assert "H162x" in fidelity
    plan = _read("docs/STAGE_162_PLAN.md")
    assert "STAGE_162_FIDELITY.md" in plan
    for ws in ("N1", "S1", "M1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage162_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_162_FIDELITY.md" in br
    assert "Stage 162 D1" in br or "test_stage162_fidelity_d1.py" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_162_FIDELITY.md" in fidelity_tail or "Stage 162 D1" in fidelity_tail


def test_stage162_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 162 D1" in api or "STAGE_162_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 162 D1" in deploy or "STAGE_162_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 162 D1" in sec or "STAGE_162_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage162_nav_n1.py" in launch
    assert "test_stage162_fidelity_d1.py" in launch
    assert "STAGE_162_FIDELITY.md" in launch
    assert "CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md" in launch or "Stage 162" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert "Finance & Accounts" in manual


def test_stage162_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_162_FIDELITY.md" in pr and "test_stage162_fidelity_d1.py" in pr
    assert "Stage 162 D1" in pr and "Stage 162 N1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_162_FIDELITY.md" in roadmap and "Stage 162 D1" in roadmap
    assert "ADR_330_STAGE162_OPEN.md" in roadmap and "STAGE_162_PLAN.md" in roadmap
    assert "CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md" in roadmap
