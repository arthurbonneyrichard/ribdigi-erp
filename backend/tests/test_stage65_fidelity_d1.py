"""Stage 65 D1 — documentation fidelity for MVP Release Candidate."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage65_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_65_FIDELITY.md")
    assert (
        "Release Candidate" in fidelity
        or "release" in fidelity.lower()
        or "pilot" in fidelity.lower()
        or "Staging" in fidelity
    )
    for name in (
        "test_release_pipeline_r1.py",
        "test_business_pilot_p1.py",
        "test_stage65_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-135" in fidelity or "ADR_135" in fidelity
    assert "H65x" in fidelity
    assert (
        "go-live" in fidelity.lower()
        or "§7" in fidelity
        or "Remaining" in fidelity
        or "deferred" in fidelity.lower()
        or "pilot" in fidelity.lower()
        or "release" in fidelity.lower()
        or "candidate" in fidelity.lower()
    )

    plan = _read("docs/STAGE_65_PLAN.md")
    assert "STAGE_65_FIDELITY.md" in plan
    for ws in ("R1", "P1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h65 = [ln for ln in plan.splitlines() if "| **H65x** |" in ln][0]
    assert "PENDING" in h65 or "COMPLETE" in h65
    assert "ADR-135" in plan or "ADR_135" in plan
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H65x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage65_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_65_FIDELITY.md" in br
    assert "Stage 65 D1" in br or "test_stage65_fidelity_d1.py" in br
    assert (
        "Stage 65 R1" in br
        or "RELEASE_PIPELINE_MVP.md" in br
        or "Stage 65 P1" in br
        or "BUSINESS_PILOT_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_65_FIDELITY.md" in fidelity_tail or "Stage 65 D1" in fidelity_tail

    for rel in (
        "docs/RELEASE_PIPELINE_MVP.md",
        "docs/BUSINESS_PILOT_MVP.md",
    ):
        assert _read(rel)


def test_stage65_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 65 D1" in api or "STAGE_65_FIDELITY.md" in api
    assert "test_stage65_fidelity_d1.py" in api or "STAGE_65_FIDELITY.md" in api
    assert (
        "RELEASE_PIPELINE_MVP.md" in api
        or "test_release_pipeline_r1.py" in api
        or "Stage 65 R1" in api
    )
    assert (
        "BUSINESS_PILOT_MVP.md" in api
        or "test_business_pilot_p1.py" in api
        or "Stage 65 P1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 65 D1" in deploy or "STAGE_65_FIDELITY.md" in deploy
    assert (
        "RELEASE_PIPELINE_MVP.md" in deploy
        or "Stage 65 R1" in deploy
        or "BUSINESS_PILOT_MVP.md" in deploy
        or "Stage 65 P1" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 65 D1" in sec or "STAGE_65_FIDELITY.md" in sec
    assert "test_release_pipeline_r1.py" in sec or "RELEASE_PIPELINE_MVP.md" in sec
    assert "test_business_pilot_p1.py" in sec or "BUSINESS_PILOT_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_release_pipeline_r1.py" in launch
    assert "test_business_pilot_p1.py" in launch
    assert "test_stage65_fidelity_d1.py" in launch
    assert "STAGE_65_FIDELITY.md" in launch
    assert "ADR-135" in launch or "ADR_135" in launch or "STAGE_65_PLAN.md" in launch


def test_stage65_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_65_FIDELITY.md" in pr
    assert "test_stage65_fidelity_d1.py" in pr
    assert "Stage 65 D1" in pr
    assert "Stage 65 R1" in pr
    assert "Stage 65 P1" in pr
    assert (
        "mvp_release_candidate_signed" in pr
        or "staging_promotion_live_claimed" in pr
        or "controlled_business_pilot_live_claimed" in pr
        or "real_workflow_feedback_claimed" in pr
        or "go_live_claimed" in pr
        or "§7" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_65_FIDELITY.md" in roadmap
    assert "Stage 65 D1" in roadmap
    assert "ADR_135_STAGE65_OPEN.md" in roadmap
    assert "STAGE_65_PLAN.md" in roadmap
    assert "test_stage65_fidelity_d1.py" in roadmap
