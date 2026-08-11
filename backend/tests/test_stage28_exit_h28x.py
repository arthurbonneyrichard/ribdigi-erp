"""Stage 28 H28x — exit criteria + freeze ADR exist."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_stage28_exit_criteria_and_freeze_adr():
    exit_doc = (ROOT / "docs" / "STAGE_28_EXIT_CRITERIA.md").read_text(encoding="utf-8")
    for token in ("R1", "G1", "A1", "C1", "D1", "H28x", "COMPLETE", "ADR-062"):
        assert token in exit_doc, token
    assert "PITR" in exit_doc or "Grafana" in exit_doc or "1000" in exit_doc
    assert "GHA" in exit_doc or "staging" in exit_doc.lower()
    assert "Open Banking" in exit_doc or "paid billing" in exit_doc.lower() or "Grafana" in exit_doc

    freeze = (ROOT / "docs" / "ADR_062_STAGE28_FREEZE.md").read_text(encoding="utf-8")
    assert "Stage 28" in freeze
    assert "frozen" in freeze.lower() or "Freeze" in freeze
    assert "Stage 29" in freeze
    assert "Stage 27" in freeze

    plan = (ROOT / "docs" / "STAGE_28_PLAN.md").read_text(encoding="utf-8")
    assert "COMPLETE" in plan
    assert "H28x" in plan
    assert "Closed" in plan or "exit met" in plan.lower() or "ADR-062" in plan
    h28_line = [ln for ln in plan.splitlines() if "| **H28x** |" in ln][0]
    assert "COMPLETE" in h28_line
    for ws in ("R1", "G1", "A1", "C1", "D1", "H28x"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws

    assert (ROOT / "docs" / "ADR_061_STAGE28_OPEN.md").is_file()
    assert (ROOT / "docs" / "STAGE_28_FIDELITY.md").is_file()
    assert (ROOT / "docs" / "STAGE_28_EXIT_CRITERIA.md").is_file()
    assert (ROOT / "docs" / "ADR_062_STAGE28_FREEZE.md").is_file()


def test_stage28_exit_listed_in_launch_and_roadmap():
    launch = (ROOT / "docs" / "LAUNCH_CHECKLIST.md").read_text(encoding="utf-8")
    assert "test_stage28_exit_h28x.py" in launch
    assert "ADR-062" in launch or "ADR_062" in launch
    assert "STAGE_28_EXIT_CRITERIA.md" in launch or "H28x" in launch

    roadmap = (ROOT / "docs" / "DEVELOPMENT_ROADMAP.md").read_text(encoding="utf-8")
    assert "STAGE_28_EXIT_CRITERIA.md" in roadmap
    assert "ADR_062_STAGE28_FREEZE.md" in roadmap
    assert "Stage 28 exit" in roadmap

    pr = (ROOT / "PRODUCTION_READINESS.md").read_text(encoding="utf-8")
    assert "STAGE_28_EXIT_CRITERIA.md" in pr or "ADR-062" in pr or "ADR_062" in pr
