"""Stage 84 D1 — documentation fidelity for Dual-Console Permission & Slice."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage84_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_84_FIDELITY.md")
    assert "Permission" in fidelity or "Slice" in fidelity or "Alias" in fidelity
    for name in (
        "test_permission_aliases_a1.py",
        "test_dashboard_slice_depth_s1.py",
        "test_stage84_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-174" in fidelity or "ADR_174" in fidelity
    assert "H84x" in fidelity
    plan = _read("docs/STAGE_84_PLAN.md")
    assert "STAGE_84_FIDELITY.md" in plan
    for ws in ("A1", "S1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws
    h84 = [ln for ln in plan.splitlines() if "| **H84x** |" in ln][0]
    assert "PENDING" in h84 or "COMPLETE" in h84
    assert any(x in plan for x in ("D1 next", "D1 complete", "H84x next", "Closed", "exit met"))


def test_stage84_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_84_FIDELITY.md" in br
    assert "Stage 84 D1" in br or "test_stage84_fidelity_d1.py" in br
    assert "Stage 84 A1" in br or "Stage 84 S1" in br or "permission alias" in br.lower()
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_84_FIDELITY.md" in fidelity_tail or "Stage 84 D1" in fidelity_tail


def test_stage84_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 84 D1" in api or "STAGE_84_FIDELITY.md" in api
    assert "test_stage84_fidelity_d1.py" in api or "STAGE_84_FIDELITY.md" in api
    assert "Stage 84 A1" in api or "inventory.view" in api or "permission alias" in api.lower()
    assert "Stage 84 S1" in api or "expenses_by_category" in api or "dashboard/credit" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 84 D1" in deploy or "STAGE_84_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 84 D1" in sec or "STAGE_84_FIDELITY.md" in sec
    assert "test_permission_aliases_a1.py" in sec or "inventory.view" in sec
    assert "test_dashboard_slice_depth_s1.py" in sec or "expenses_by_category" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_permission_aliases_a1.py" in launch
    assert "test_dashboard_slice_depth_s1.py" in launch
    assert "test_stage84_fidelity_d1.py" in launch
    assert "STAGE_84_FIDELITY.md" in launch
    assert "ADR-174" in launch or "ADR_174" in launch or "STAGE_84_PLAN.md" in launch


def test_stage84_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_84_FIDELITY.md" in pr and "test_stage84_fidelity_d1.py" in pr
    assert "Stage 84 D1" in pr and "Stage 84 A1" in pr and "Stage 84 S1" in pr
    assert (
        "user_store_membership_claimed" in pr
        or "ADR-005" in pr
        or "go_live_claimed" in pr
        or "Remaining" in pr
    )
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_84_FIDELITY.md" in roadmap and "Stage 84 D1" in roadmap
    assert "ADR_174_STAGE84_OPEN.md" in roadmap and "STAGE_84_PLAN.md" in roadmap
    assert "test_stage84_fidelity_d1.py" in roadmap
