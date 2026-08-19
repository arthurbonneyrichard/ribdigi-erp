"""Stage 28 open — plan + ADR-061 exist; Stage 27 freeze remains."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_stage28_plan_and_open_adr():
    plan = (ROOT / "docs" / "STAGE_28_PLAN.md").read_text(encoding="utf-8")
    assert "Staging Certification" in plan or "PITR" in plan
    assert "ADR-061" in plan or "ADR_061" in plan
    for ws in ("R1", "G1", "A1", "C1", "D1", "H28x"):
        assert f"| **{ws}** |" in plan, ws
    assert (
        "PENDING" in plan
        or "R1 next" in plan
        or "R1 complete" in plan
        or "G1 next" in plan
        or "G1 complete" in plan
        or "A1 next" in plan
        or "A1 complete" in plan
        or "C1 next" in plan
        or "C1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H28x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )
    assert "PITR" in plan or "drill" in plan.lower()
    assert "GHA" in plan or "staging" in plan.lower()
    assert "Grafana" in plan or "Alertmanager" in plan
    assert "1000" in plan or "VU" in plan
    assert "paid billing" in plan.lower() or "ADR-002" in plan
    assert "ci.yml" in plan.lower() or "Stage 18 C1" in plan

    adr = (ROOT / "docs" / "ADR_061_STAGE28_OPEN.md").read_text(encoding="utf-8")
    assert "Stage 28" in adr
    assert "STAGE_28_PLAN.md" in adr
    assert "R1" in adr and "H28x" in adr
    assert "ADR-060" in adr or "ADR_060" in adr
    assert "Staging Certification" in adr or "PITR" in adr
    assert "Grafana" in adr or "1000" in adr


def test_stage27_freeze_amended_for_stage28():
    freeze = (ROOT / "docs" / "ADR_060_STAGE27_FREEZE.md").read_text(encoding="utf-8")
    assert "Amendment" in freeze
    assert "ADR-061" in freeze or "ADR_061" in freeze
    assert "STAGE_28_PLAN.md" in freeze
    assert "frozen" in freeze.lower()


def test_stage28_listed_in_launch_and_roadmap():
    launch = (ROOT / "docs" / "LAUNCH_CHECKLIST.md").read_text(encoding="utf-8")
    assert "STAGE_28_PLAN.md" in launch
    assert "ADR-061" in launch or "ADR_061" in launch

    roadmap = (ROOT / "docs" / "DEVELOPMENT_ROADMAP.md").read_text(encoding="utf-8")
    assert "ADR_061_STAGE28_OPEN.md" in roadmap
    assert "STAGE_28_PLAN.md" in roadmap
    assert "Stage 28 open" in roadmap
