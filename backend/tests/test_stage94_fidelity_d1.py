"""Stage 94 D1 — documentation fidelity for House Discovery & Runtime Assurance Ops."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage94_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_94_FIDELITY.md")
    assert "Discovery" in fidelity or "Assurance" in fidelity
    for name in (
        "test_stage94_staff_discovery_w1.py",
        "test_stage94_configuration_integrity_h1.py",
        "test_stage94_console_state_t2.py",
        "test_stage94_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-194" in fidelity or "ADR_194" in fidelity
    assert "H94x" in fidelity
    plan = _read("docs/STAGE_94_PLAN.md")
    assert "STAGE_94_FIDELITY.md" in plan
    for ws in ("W1", "H1", "T2", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws
    h94 = [ln for ln in plan.splitlines() if "| **H94x** |" in ln][0]
    assert "PENDING" in h94 or "COMPLETE" in h94
    assert any(x in plan for x in ("D1 next", "D1 complete", "H94x next", "Closed", "exit met"))


def test_stage94_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_94_FIDELITY.md" in br
    assert "Stage 94 D1" in br or "test_stage94_fidelity_d1.py" in br
    assert "Stage 94 W1" in br or "Stage 94 H1" in br or "Stage 94 T2" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_94_FIDELITY.md" in fidelity_tail or "Stage 94 D1" in fidelity_tail


def test_stage94_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 94 D1" in api or "STAGE_94_FIDELITY.md" in api
    assert "test_stage94_fidelity_d1.py" in api or "STAGE_94_FIDELITY.md" in api
    assert "Stage 94 W1" in api or "platform/users" in api
    assert "Stage 94 H1" in api or "runtime_identity" in api
    assert "Stage 94 T2" in api or "at-risk" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 94 D1" in deploy or "STAGE_94_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 94 D1" in sec or "STAGE_94_FIDELITY.md" in sec
    assert "test_stage94_staff_discovery_w1.py" in sec or "platform/users" in sec
    assert "test_stage94_configuration_integrity_h1.py" in sec or "runtime_identity" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage94_staff_discovery_w1.py" in launch
    assert "test_stage94_configuration_integrity_h1.py" in launch
    assert "test_stage94_console_state_t2.py" in launch
    assert "test_stage94_fidelity_d1.py" in launch
    assert "STAGE_94_FIDELITY.md" in launch
    assert "ADR-194" in launch or "ADR_194" in launch or "STAGE_94_PLAN.md" in launch


def test_stage94_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_94_FIDELITY.md" in pr and "test_stage94_fidelity_d1.py" in pr
    assert "Stage 94 D1" in pr and "Stage 94 W1" in pr and "Stage 94 H1" in pr and "Stage 94 T2" in pr
    assert (
        "user_store_membership_claimed" in pr
        or "ADR-005" in pr
        or "go_live_claimed" in pr
        or "Remaining" in pr
    )
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_94_FIDELITY.md" in roadmap and "Stage 94 D1" in roadmap
    assert "ADR_194_STAGE94_OPEN.md" in roadmap and "STAGE_94_PLAN.md" in roadmap
    assert "test_stage94_fidelity_d1.py" in roadmap
