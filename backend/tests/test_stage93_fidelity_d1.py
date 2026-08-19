"""Stage 93 D1 — documentation fidelity for House Navigation & Runtime Ops."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage93_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_93_FIDELITY.md")
    assert "Navigation" in fidelity or "Runtime" in fidelity
    for name in (
        "test_stage93_roster_navigation_m1.py",
        "test_stage93_staff_integrity_j1.py",
        "test_stage93_runtime_posture_v1.py",
        "test_stage93_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-192" in fidelity or "ADR_192" in fidelity
    assert "H93x" in fidelity
    plan = _read("docs/STAGE_93_PLAN.md")
    assert "STAGE_93_FIDELITY.md" in plan
    for ws in ("M1", "J1", "V1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws
    h93 = [ln for ln in plan.splitlines() if "| **H93x** |" in ln][0]
    assert "PENDING" in h93 or "COMPLETE" in h93
    assert any(x in plan for x in ("D1 next", "D1 complete", "H93x next", "Closed", "exit met"))


def test_stage93_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_93_FIDELITY.md" in br
    assert "Stage 93 D1" in br or "test_stage93_fidelity_d1.py" in br
    assert "Stage 93 M1" in br or "Stage 93 J1" in br or "Stage 93 V1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_93_FIDELITY.md" in fidelity_tail or "Stage 93 D1" in fidelity_tail


def test_stage93_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 93 D1" in api or "STAGE_93_FIDELITY.md" in api
    assert "test_stage93_fidelity_d1.py" in api or "STAGE_93_FIDELITY.md" in api
    assert "Stage 93 M1" in api or "created_this_month" in api or "/platform/industries" in api
    assert "Stage 93 J1" in api or "last_invite_delivery" in api or "verified_at" in api
    assert "Stage 93 V1" in api or "number_format" in api or "house_runtime" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 93 D1" in deploy or "STAGE_93_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 93 D1" in sec or "STAGE_93_FIDELITY.md" in sec
    assert "test_stage93_roster_navigation_m1.py" in sec or "created_this_month" in sec
    assert "test_stage93_runtime_posture_v1.py" in sec or "house_runtime" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage93_roster_navigation_m1.py" in launch
    assert "test_stage93_staff_integrity_j1.py" in launch
    assert "test_stage93_runtime_posture_v1.py" in launch
    assert "test_stage93_fidelity_d1.py" in launch
    assert "STAGE_93_FIDELITY.md" in launch
    assert "ADR-192" in launch or "ADR_192" in launch or "STAGE_93_PLAN.md" in launch


def test_stage93_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_93_FIDELITY.md" in pr and "test_stage93_fidelity_d1.py" in pr
    assert "Stage 93 D1" in pr and "Stage 93 M1" in pr and "Stage 93 J1" in pr and "Stage 93 V1" in pr
    assert (
        "user_store_membership_claimed" in pr
        or "ADR-005" in pr
        or "go_live_claimed" in pr
        or "Remaining" in pr
    )
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_93_FIDELITY.md" in roadmap and "Stage 93 D1" in roadmap
    assert "ADR_192_STAGE93_OPEN.md" in roadmap and "STAGE_93_PLAN.md" in roadmap
    assert "test_stage93_fidelity_d1.py" in roadmap
