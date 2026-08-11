"""Stage 40 H40x — exit criteria + freeze ADR exist."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_stage40_exit_criteria_and_freeze_adr():
    exit_doc = (ROOT / "docs" / "STAGE_40_EXIT_CRITERIA.md").read_text(encoding="utf-8")
    for token in ("U1", "S1", "D1", "H40x", "COMPLETE", "ADR-086"):
        assert token in exit_doc, token
    assert (
        "Availability" in exit_doc
        or "Supply-Chain" in exit_doc
        or "uptime" in exit_doc.lower()
        or "SBOM" in exit_doc
        or "status" in exit_doc.lower()
    )
    assert "Deferred" in exit_doc or "Remaining" in exit_doc or "SBOM" in exit_doc
    assert "CRITICAL" in exit_doc or "MISSING" in exit_doc or "Sign-off" in exit_doc

    freeze = (ROOT / "docs" / "ADR_086_STAGE40_FREEZE.md").read_text(encoding="utf-8")
    assert "Stage 40" in freeze
    assert "frozen" in freeze.lower() or "Freeze" in freeze
    assert "Stage 41" in freeze
    assert "Stage 39" in freeze
    assert "Accepted" in freeze

    plan = (ROOT / "docs" / "STAGE_40_PLAN.md").read_text(encoding="utf-8")
    assert "COMPLETE" in plan
    assert "H40x" in plan
    assert "Closed" in plan or "exit met" in plan.lower() or "ADR-086" in plan
    h40_line = [ln for ln in plan.splitlines() if "| **H40x** |" in ln][0]
    assert "COMPLETE" in h40_line
    for ws in ("U1", "S1", "D1", "H40x"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws

    assert (ROOT / "docs" / "ADR_085_STAGE40_OPEN.md").is_file()
    assert (ROOT / "docs" / "STAGE_40_FIDELITY.md").is_file()
    assert (ROOT / "docs" / "STAGE_40_EXIT_CRITERIA.md").is_file()
    assert (ROOT / "docs" / "ADR_086_STAGE40_FREEZE.md").is_file()


def test_stage40_exit_listed_in_launch_and_roadmap():
    launch = (ROOT / "docs" / "LAUNCH_CHECKLIST.md").read_text(encoding="utf-8")
    assert "test_stage40_exit_h40x.py" in launch
    assert "ADR-086" in launch or "ADR_086" in launch
    assert "STAGE_40_EXIT_CRITERIA.md" in launch or "H40x" in launch

    roadmap = (ROOT / "docs" / "DEVELOPMENT_ROADMAP.md").read_text(encoding="utf-8")
    assert "STAGE_40_EXIT_CRITERIA.md" in roadmap
    assert "ADR_086_STAGE40_FREEZE.md" in roadmap
    assert "Stage 40 exit" in roadmap

    pr = (ROOT / "PRODUCTION_READINESS.md").read_text(encoding="utf-8")
    assert "STAGE_40_EXIT_CRITERIA.md" in pr or "ADR-086" in pr or "ADR_086" in pr

    sec = (ROOT / "docs" / "SECURITY_GUIDE.md").read_text(encoding="utf-8")
    assert "ADR-086" in sec or "ADR_086" in sec or "test_stage40_exit_h40x.py" in sec
    assert "STAGE_40_EXIT_CRITERIA.md" in sec or "H40x" in sec or "Stage 40 exit" in sec
