"""Stage 82 D1 — documentation fidelity for Dual-Console Surface Parity."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage82_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_82_FIDELITY.md")
    assert "Dashboard" in fidelity or "Plans" in fidelity or "Surface" in fidelity
    for name in (
        "test_dashboard_slices_c1.py",
        "test_platform_plans_p1.py",
        "test_stage82_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-170" in fidelity or "ADR_170" in fidelity
    assert "H82x" in fidelity
    plan = _read("docs/STAGE_82_PLAN.md")
    assert "STAGE_82_FIDELITY.md" in plan
    for ws in ("C1", "P1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws
    h82 = [ln for ln in plan.splitlines() if "| **H82x** |" in ln][0]
    assert "PENDING" in h82 or "COMPLETE" in h82
    assert any(x in plan for x in ("D1 next", "D1 complete", "H82x next", "Closed", "exit met"))


def test_stage82_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_82_FIDELITY.md" in br
    assert "Stage 82 D1" in br or "test_stage82_fidelity_d1.py" in br
    assert "Stage 82 C1" in br or "Stage 82 P1" in br or "dashboard/sales-trend" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_82_FIDELITY.md" in fidelity_tail or "Stage 82 D1" in fidelity_tail


def test_stage82_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 82 D1" in api or "STAGE_82_FIDELITY.md" in api
    assert "test_stage82_fidelity_d1.py" in api or "STAGE_82_FIDELITY.md" in api
    assert "Stage 82 C1" in api or "dashboard/sales-trend" in api
    assert "Stage 82 P1" in api or "platform/plans" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 82 D1" in deploy or "STAGE_82_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 82 D1" in sec or "STAGE_82_FIDELITY.md" in sec
    assert "test_dashboard_slices_c1.py" in sec or "dashboard/sales-trend" in sec
    assert "test_platform_plans_p1.py" in sec or "platform/plans" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_dashboard_slices_c1.py" in launch
    assert "test_platform_plans_p1.py" in launch
    assert "test_stage82_fidelity_d1.py" in launch
    assert "STAGE_82_FIDELITY.md" in launch
    assert "ADR-170" in launch or "ADR_170" in launch or "STAGE_82_PLAN.md" in launch


def test_stage82_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_82_FIDELITY.md" in pr and "test_stage82_fidelity_d1.py" in pr
    assert "Stage 82 D1" in pr and "Stage 82 C1" in pr and "Stage 82 P1" in pr
    assert (
        "mrr_fabricated_claimed" in pr
        or "billing_complete_claimed" in pr
        or "go_live_claimed" in pr
        or "Remaining" in pr
    )
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_82_FIDELITY.md" in roadmap and "Stage 82 D1" in roadmap
    assert "ADR_170_STAGE82_OPEN.md" in roadmap and "STAGE_82_PLAN.md" in roadmap
    assert "test_stage82_fidelity_d1.py" in roadmap
