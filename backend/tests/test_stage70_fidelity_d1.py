"""Stage 70 D1 — documentation fidelity for First Commercial Day."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage70_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_70_FIDELITY.md")
    assert (
        "First Commercial Day" in fidelity
        or "Closeout" in fidelity
        or "go-live" in fidelity.lower()
    )
    for name in (
        "test_first_commercial_day_f1.py",
        "test_commercial_golive_closeout_g1.py",
        "test_stage70_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-146" in fidelity or "ADR_146" in fidelity
    assert "H70x" in fidelity
    assert (
        "first_commercial_day" in fidelity.lower()
        or "go_live" in fidelity.lower()
        or "§7" in fidelity
        or "section" in fidelity.lower()
    )

    plan = _read("docs/STAGE_70_PLAN.md")
    assert "STAGE_70_FIDELITY.md" in plan
    for ws in ("F1", "G1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h70 = [ln for ln in plan.splitlines() if "| **H70x** |" in ln][0]
    assert "PENDING" in h70 or "COMPLETE" in h70
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H70x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage70_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_70_FIDELITY.md" in br
    assert "Stage 70 D1" in br or "test_stage70_fidelity_d1.py" in br
    assert (
        "Stage 70 F1" in br
        or "FIRST_COMMERCIAL_DAY_MVP.md" in br
        or "Stage 70 G1" in br
        or "COMMERCIAL_GOLIVE_CLOSEOUT_MVP.md" in br
    )
    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_70_FIDELITY.md" in fidelity_tail or "Stage 70 D1" in fidelity_tail
    for rel in ("docs/FIRST_COMMERCIAL_DAY_MVP.md", "docs/COMMERCIAL_GOLIVE_CLOSEOUT_MVP.md"):
        assert _read(rel)


def test_stage70_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 70 D1" in api or "STAGE_70_FIDELITY.md" in api
    assert "test_stage70_fidelity_d1.py" in api or "STAGE_70_FIDELITY.md" in api
    assert "Stage 70 F1" in api or "FIRST_COMMERCIAL_DAY_MVP.md" in api
    assert "Stage 70 G1" in api or "COMMERCIAL_GOLIVE_CLOSEOUT_MVP.md" in api

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 70 D1" in deploy or "STAGE_70_FIDELITY.md" in deploy

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 70 D1" in sec or "STAGE_70_FIDELITY.md" in sec
    assert "test_first_commercial_day_f1.py" in sec or "FIRST_COMMERCIAL_DAY_MVP.md" in sec
    assert "test_commercial_golive_closeout_g1.py" in sec or "COMMERCIAL_GOLIVE_CLOSEOUT_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_first_commercial_day_f1.py" in launch
    assert "test_commercial_golive_closeout_g1.py" in launch
    assert "test_stage70_fidelity_d1.py" in launch
    assert "STAGE_70_FIDELITY.md" in launch
    assert "ADR-146" in launch or "ADR_146" in launch or "STAGE_70_PLAN.md" in launch


def test_stage70_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_70_FIDELITY.md" in pr
    assert "test_stage70_fidelity_d1.py" in pr
    assert "Stage 70 D1" in pr
    assert "Stage 70 F1" in pr
    assert "Stage 70 G1" in pr
    assert (
        "first_commercial_day_claimed" in pr
        or "go_live_claimed" in pr
        or "section_7_signed" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_70_FIDELITY.md" in roadmap
    assert "Stage 70 D1" in roadmap
    assert "ADR_146_STAGE70_OPEN.md" in roadmap
    assert "STAGE_70_PLAN.md" in roadmap
    assert "test_stage70_fidelity_d1.py" in roadmap
