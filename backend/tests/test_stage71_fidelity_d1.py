"""Stage 71 D1 — documentation fidelity for Commercial Steady-State."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage71_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_71_FIDELITY.md")
    assert (
        "Steady-State" in fidelity
        or "Acceptance" in fidelity
        or "acceptance" in fidelity.lower()
    )
    for name in (
        "test_steady_state_ops_s1.py",
        "test_commercial_acceptance_a1.py",
        "test_stage71_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-148" in fidelity or "ADR_148" in fidelity
    assert "H71x" in fidelity
    assert (
        "steady_state" in fidelity.lower()
        or "acceptance" in fidelity.lower()
        or "go_live" in fidelity.lower()
    )

    plan = _read("docs/STAGE_71_PLAN.md")
    assert "STAGE_71_FIDELITY.md" in plan
    for ws in ("S1", "A1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h71 = [ln for ln in plan.splitlines() if "| **H71x** |" in ln][0]
    assert "PENDING" in h71 or "COMPLETE" in h71
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H71x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage71_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_71_FIDELITY.md" in br
    assert "Stage 71 D1" in br or "test_stage71_fidelity_d1.py" in br
    assert (
        "Stage 71 S1" in br
        or "STEADY_STATE_OPS_MVP.md" in br
        or "Stage 71 A1" in br
        or "COMMERCIAL_ACCEPTANCE_MVP.md" in br
    )
    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_71_FIDELITY.md" in fidelity_tail or "Stage 71 D1" in fidelity_tail
    for rel in ("docs/STEADY_STATE_OPS_MVP.md", "docs/COMMERCIAL_ACCEPTANCE_MVP.md"):
        assert _read(rel)


def test_stage71_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 71 D1" in api or "STAGE_71_FIDELITY.md" in api
    assert "test_stage71_fidelity_d1.py" in api or "STAGE_71_FIDELITY.md" in api
    assert "Stage 71 S1" in api or "STEADY_STATE_OPS_MVP.md" in api
    assert "Stage 71 A1" in api or "COMMERCIAL_ACCEPTANCE_MVP.md" in api

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 71 D1" in deploy or "STAGE_71_FIDELITY.md" in deploy

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 71 D1" in sec or "STAGE_71_FIDELITY.md" in sec
    assert "test_steady_state_ops_s1.py" in sec or "STEADY_STATE_OPS_MVP.md" in sec
    assert "test_commercial_acceptance_a1.py" in sec or "COMMERCIAL_ACCEPTANCE_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_steady_state_ops_s1.py" in launch
    assert "test_commercial_acceptance_a1.py" in launch
    assert "test_stage71_fidelity_d1.py" in launch
    assert "STAGE_71_FIDELITY.md" in launch
    assert "ADR-148" in launch or "ADR_148" in launch or "STAGE_71_PLAN.md" in launch


def test_stage71_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_71_FIDELITY.md" in pr
    assert "test_stage71_fidelity_d1.py" in pr
    assert "Stage 71 D1" in pr
    assert "Stage 71 S1" in pr
    assert "Stage 71 A1" in pr
    assert (
        "steady_state_ops_claimed" in pr
        or "commercial_acceptance_claimed" in pr
        or "go_live_claimed" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_71_FIDELITY.md" in roadmap
    assert "Stage 71 D1" in roadmap
    assert "ADR_148_STAGE71_OPEN.md" in roadmap
    assert "STAGE_71_PLAN.md" in roadmap
    assert "test_stage71_fidelity_d1.py" in roadmap
