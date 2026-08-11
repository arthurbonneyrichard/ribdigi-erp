"""Stage 81 D1 — documentation fidelity for Dual-Console Admin."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage81_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_81_FIDELITY.md")
    assert "Admin" in fidelity and ("Roles" in fidelity or "Store" in fidelity)
    for name in (
        "test_admin_console_a1.py",
        "test_store_scoped_manager_s1.py",
        "test_stage81_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-168" in fidelity or "ADR_168" in fidelity
    assert "H81x" in fidelity
    plan = _read("docs/STAGE_81_PLAN.md")
    assert "STAGE_81_FIDELITY.md" in plan
    for ws in ("A1", "S1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws
    h81 = [ln for ln in plan.splitlines() if "| **H81x** |" in ln][0]
    assert "PENDING" in h81 or "COMPLETE" in h81
    assert any(x in plan for x in ("D1 next", "D1 complete", "H81x next", "Closed", "exit met"))


def test_stage81_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_81_FIDELITY.md" in br
    assert "Stage 81 D1" in br or "test_stage81_fidelity_d1.py" in br
    assert "Stage 81 A1" in br or "Stage 81 S1" in br or "admin/roles" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_81_FIDELITY.md" in fidelity_tail or "Stage 81 D1" in fidelity_tail


def test_stage81_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 81 D1" in api or "STAGE_81_FIDELITY.md" in api
    assert "test_stage81_fidelity_d1.py" in api or "STAGE_81_FIDELITY.md" in api
    assert "Stage 81 A1" in api or "admin/roles" in api
    assert "Stage 81 S1" in api or "store_scope" in api or "manager" in api.lower()
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 81 D1" in deploy or "STAGE_81_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 81 D1" in sec or "STAGE_81_FIDELITY.md" in sec
    assert "test_admin_console_a1.py" in sec or "admin/roles" in sec
    assert "test_store_scoped_manager_s1.py" in sec or "store_scope" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_admin_console_a1.py" in launch
    assert "test_store_scoped_manager_s1.py" in launch
    assert "test_stage81_fidelity_d1.py" in launch
    assert "STAGE_81_FIDELITY.md" in launch
    assert "ADR-168" in launch or "ADR_168" in launch or "STAGE_81_PLAN.md" in launch


def test_stage81_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_81_FIDELITY.md" in pr and "test_stage81_fidelity_d1.py" in pr
    assert "Stage 81 D1" in pr and "Stage 81 A1" in pr and "Stage 81 S1" in pr
    assert (
        "user_store_membership_claimed" in pr
        or "ADR-005" in pr
        or "go_live_claimed" in pr
        or "Remaining" in pr
    )
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_81_FIDELITY.md" in roadmap and "Stage 81 D1" in roadmap
    assert "ADR_168_STAGE81_OPEN.md" in roadmap and "STAGE_81_PLAN.md" in roadmap
    assert "test_stage81_fidelity_d1.py" in roadmap
