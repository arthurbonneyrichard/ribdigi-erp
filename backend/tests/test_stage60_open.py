"""Stage 60 open — plan + ADR-125 exist; Stage 59 freeze remains."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_stage60_plan_and_open_adr():
    plan = (ROOT / "docs" / "STAGE_60_PLAN.md").read_text(encoding="utf-8")
    assert (
        "Manufacturing" in plan
        or "MRP" in plan
        or "Tax" in plan
        or "GST" in plan
        or "VAT" in plan
    )
    assert "ADR-125" in plan or "ADR_125" in plan
    for ws in ("M1", "T1", "D1", "H60x"):
        assert f"| **{ws}** |" in plan, ws
    assert (
        "PENDING" in plan
        or "M1 next" in plan
        or "M1 complete" in plan
        or "T1 complete" in plan
        or "T1 next" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H60x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )
    assert "Manufacturing" in plan or "MRP" in plan
    assert "Tax" in plan or "GST" in plan or "VAT" in plan
    assert "ci.yml" in plan.lower() or "Stage 18 C1" in plan
    assert "Stage 59" in plan

    adr = (ROOT / "docs" / "ADR_125_STAGE60_OPEN.md").read_text(encoding="utf-8")
    assert "Stage 60" in adr
    assert "STAGE_60_PLAN.md" in adr
    assert "M1" in adr and "H60x" in adr
    assert "ADR-124" in adr or "ADR_124" in adr
    assert (
        "Manufacturing" in adr
        or "MRP" in adr
        or "Tax" in adr
        or "GST" in adr
    )
    assert "MVP" in adr


def test_stage59_freeze_amended_for_stage60():
    freeze = (ROOT / "docs" / "ADR_124_STAGE59_FREEZE.md").read_text(encoding="utf-8")
    assert "Amendment" in freeze
    assert "ADR-125" in freeze or "ADR_125" in freeze
    assert "STAGE_60_PLAN.md" in freeze
    assert "frozen" in freeze.lower()


def test_stage60_listed_in_launch_and_roadmap():
    launch = (ROOT / "docs" / "LAUNCH_CHECKLIST.md").read_text(encoding="utf-8")
    assert "STAGE_60_PLAN.md" in launch
    assert "ADR-125" in launch or "ADR_125" in launch

    roadmap = (ROOT / "docs" / "DEVELOPMENT_ROADMAP.md").read_text(encoding="utf-8")
    assert "ADR_125_STAGE60_OPEN.md" in roadmap
    assert "STAGE_60_PLAN.md" in roadmap
    assert "Stage 60 open" in roadmap
