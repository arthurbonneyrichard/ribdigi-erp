"""Stage 61 open — plan + ADR-127 exist; Stage 60 freeze remains."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_stage61_plan_and_open_adr():
    plan = (ROOT / "docs" / "STAGE_61_PLAN.md").read_text(encoding="utf-8")
    assert (
        "Fintech" in plan
        or "fintech" in plan.lower()
        or "lending" in plan.lower()
        or "Supply" in plan
        or "supply chain" in plan.lower()
    )
    assert "ADR-127" in plan or "ADR_127" in plan
    for ws in ("F1", "S1", "D1", "H61x"):
        assert f"| **{ws}** |" in plan, ws
    assert (
        "PENDING" in plan
        or "F1 next" in plan
        or "F1 complete" in plan
        or "S1 next" in plan
        or "S1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H61x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )
    assert "Fintech" in plan or "fintech" in plan.lower() or "lending" in plan.lower()
    assert "Supply" in plan or "supply" in plan.lower()
    assert "ci.yml" in plan.lower() or "Stage 18 C1" in plan
    assert "Stage 60" in plan

    adr = (ROOT / "docs" / "ADR_127_STAGE61_OPEN.md").read_text(encoding="utf-8")
    assert "Stage 61" in adr
    assert "STAGE_61_PLAN.md" in adr
    assert "F1" in adr and "H61x" in adr
    assert "ADR-126" in adr or "ADR_126" in adr
    assert (
        "Fintech" in adr
        or "fintech" in adr.lower()
        or "Supply" in adr
        or "lending" in adr.lower()
    )
    assert "MVP" in adr


def test_stage60_freeze_amended_for_stage61():
    freeze = (ROOT / "docs" / "ADR_126_STAGE60_FREEZE.md").read_text(encoding="utf-8")
    assert "Amendment" in freeze
    assert "ADR-127" in freeze or "ADR_127" in freeze
    assert "STAGE_61_PLAN.md" in freeze
    assert "frozen" in freeze.lower()


def test_stage61_listed_in_launch_and_roadmap():
    launch = (ROOT / "docs" / "LAUNCH_CHECKLIST.md").read_text(encoding="utf-8")
    assert "STAGE_61_PLAN.md" in launch
    assert "ADR-127" in launch or "ADR_127" in launch

    roadmap = (ROOT / "docs" / "DEVELOPMENT_ROADMAP.md").read_text(encoding="utf-8")
    assert "ADR_127_STAGE61_OPEN.md" in roadmap
    assert "STAGE_61_PLAN.md" in roadmap
    assert "Stage 61 open" in roadmap
