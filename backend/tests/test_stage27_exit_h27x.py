"""Stage 27 H27x — exit criteria + freeze ADR exist."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_stage27_exit_criteria_and_freeze_adr():
    exit_doc = (ROOT / "docs" / "STAGE_27_EXIT_CRITERIA.md").read_text(encoding="utf-8")
    for token in ("B1", "P1", "S1", "L1", "D1", "H27x", "COMPLETE", "ADR-060"):
        assert token in exit_doc, token
    assert "BR-16" in exit_doc or "ribbak" in exit_doc.lower() or "PgBouncer" in exit_doc
    assert "PgBouncer" in exit_doc or "OWASP" in exit_doc or "Launch" in exit_doc
    assert "Open Banking" in exit_doc or "paid billing" in exit_doc.lower() or "Grafana" in exit_doc

    freeze = (ROOT / "docs" / "ADR_060_STAGE27_FREEZE.md").read_text(encoding="utf-8")
    assert "Stage 27" in freeze
    assert "frozen" in freeze.lower() or "Freeze" in freeze
    assert "Stage 28" in freeze
    assert "Stage 26" in freeze

    plan = (ROOT / "docs" / "STAGE_27_PLAN.md").read_text(encoding="utf-8")
    assert "COMPLETE" in plan
    assert "H27x" in plan
    assert "Closed" in plan or "exit met" in plan.lower() or "ADR-060" in plan
    h27_line = [ln for ln in plan.splitlines() if "| **H27x** |" in ln][0]
    assert "COMPLETE" in h27_line
    for ws in ("B1", "P1", "S1", "L1", "D1", "H27x"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws

    assert (ROOT / "docs" / "ADR_059_STAGE27_OPEN.md").is_file()
    assert (ROOT / "docs" / "STAGE_27_FIDELITY.md").is_file()
    assert (ROOT / "docs" / "STAGE_27_EXIT_CRITERIA.md").is_file()
    assert (ROOT / "docs" / "ADR_060_STAGE27_FREEZE.md").is_file()


def test_stage27_exit_listed_in_launch_and_roadmap():
    launch = (ROOT / "docs" / "LAUNCH_CHECKLIST.md").read_text(encoding="utf-8")
    assert "test_stage27_exit_h27x.py" in launch
    assert "ADR-060" in launch or "ADR_060" in launch
    assert "STAGE_27_EXIT_CRITERIA.md" in launch or "H27x" in launch

    roadmap = (ROOT / "docs" / "DEVELOPMENT_ROADMAP.md").read_text(encoding="utf-8")
    assert "STAGE_27_EXIT_CRITERIA.md" in roadmap
    assert "ADR_060_STAGE27_FREEZE.md" in roadmap
    assert "Stage 27 exit" in roadmap

    pr = (ROOT / "PRODUCTION_READINESS.md").read_text(encoding="utf-8")
    assert "STAGE_27_EXIT_CRITERIA.md" in pr or "ADR-060" in pr or "ADR_060" in pr
