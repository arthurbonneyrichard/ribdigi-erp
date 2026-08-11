"""Stage 25 open — plan + ADR-055 exist; Stage 24 freeze remains."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_stage25_plan_and_open_adr():
    plan = (ROOT / "docs" / "STAGE_25_PLAN.md").read_text(encoding="utf-8")
    assert "Actuals" in plan or "Business Insights" in plan
    assert "ADR-055" in plan or "ADR_055" in plan
    for ws in ("P1", "X1", "B1", "U1", "D1", "H25x"):
        assert f"| **{ws}** |" in plan, ws
    assert (
        "PENDING" in plan
        or "P1 next" in plan
        or "X1 next" in plan
        or "B1 next" in plan
        or "U1 next" in plan
        or "D1 next" in plan
        or "H25x next" in plan
        or "P1 complete" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )
    assert "Actual Inventory" in plan
    assert "Actual Purchases" in plan
    assert "Business Insights" in plan
    assert "WAL" in plan or "PITR" in plan or "Prophet" in plan

    adr = (ROOT / "docs" / "ADR_055_STAGE25_OPEN.md").read_text(encoding="utf-8")
    assert "Stage 25" in adr
    assert "STAGE_25_PLAN.md" in adr
    assert "P1" in adr and "H25x" in adr
    assert "ADR-054" in adr or "ADR_054" in adr
    assert "Actual Inventory" in adr
    assert "Business Insights" in adr


def test_stage24_freeze_amended_for_stage25():
    freeze = (ROOT / "docs" / "ADR_054_STAGE24_FREEZE.md").read_text(encoding="utf-8")
    assert "Amendment" in freeze
    assert "ADR-055" in freeze or "ADR_055" in freeze
    assert "STAGE_25_PLAN.md" in freeze
    assert "frozen" in freeze.lower()


def test_stage25_listed_in_launch_and_roadmap():
    launch = (ROOT / "docs" / "LAUNCH_CHECKLIST.md").read_text(encoding="utf-8")
    assert "STAGE_25_PLAN.md" in launch
    assert "ADR-055" in launch or "ADR_055" in launch

    roadmap = (ROOT / "docs" / "DEVELOPMENT_ROADMAP.md").read_text(encoding="utf-8")
    assert "ADR_055_STAGE25_OPEN.md" in roadmap
    assert "STAGE_25_PLAN.md" in roadmap
    assert "Stage 25 open" in roadmap
