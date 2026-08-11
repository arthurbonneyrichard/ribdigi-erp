"""Stage 60 H60x — exit criteria + freeze ADR exist."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_stage60_exit_criteria_and_freeze_adr():
    exit_doc = (ROOT / "docs" / "STAGE_60_EXIT_CRITERIA.md").read_text(encoding="utf-8")
    for token in ("M1", "T1", "D1", "H60x", "COMPLETE", "ADR-126"):
        assert token in exit_doc, token
    assert (
        "Manufacturing" in exit_doc
        or "MRP" in exit_doc
        or "Tax" in exit_doc
        or "GST" in exit_doc
        or "VAT" in exit_doc
    )
    assert (
        "Deferred" in exit_doc
        or "Remaining" in exit_doc
        or "mrp" in exit_doc.lower()
        or "tax" in exit_doc.lower()
        or "manufactur" in exit_doc.lower()
    )
    assert "CRITICAL" in exit_doc or "MISSING" in exit_doc or "Sign-off" in exit_doc

    freeze = (ROOT / "docs" / "ADR_126_STAGE60_FREEZE.md").read_text(encoding="utf-8")
    assert "Stage 60" in freeze
    assert "frozen" in freeze.lower() or "Freeze" in freeze
    assert "Stage 61" in freeze  # next stage named explicitly
    assert "Stage 59" in freeze  # prior stage named explicitly
    assert "Accepted" in freeze

    plan = (ROOT / "docs" / "STAGE_60_PLAN.md").read_text(encoding="utf-8")
    assert "COMPLETE" in plan
    assert "H60x" in plan
    assert "Closed" in plan or "exit met" in plan.lower() or "ADR-126" in plan
    h60_line = [ln for ln in plan.splitlines() if "| **H60x** |" in ln][0]
    assert "COMPLETE" in h60_line
    for ws in ("M1", "T1", "D1", "H60x"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws

    assert (ROOT / "docs" / "ADR_125_STAGE60_OPEN.md").is_file()
    assert (ROOT / "docs" / "STAGE_60_FIDELITY.md").is_file()
    assert (ROOT / "docs" / "STAGE_60_EXIT_CRITERIA.md").is_file()
    assert (ROOT / "docs" / "ADR_126_STAGE60_FREEZE.md").is_file()


def test_stage60_exit_listed_in_launch_and_roadmap():
    launch = (ROOT / "docs" / "LAUNCH_CHECKLIST.md").read_text(encoding="utf-8")
    assert "test_stage60_exit_h60x.py" in launch
    assert "ADR-126" in launch or "ADR_126" in launch
    assert "STAGE_60_EXIT_CRITERIA.md" in launch or "H60x" in launch

    roadmap = (ROOT / "docs" / "DEVELOPMENT_ROADMAP.md").read_text(encoding="utf-8")
    assert "STAGE_60_EXIT_CRITERIA.md" in roadmap
    assert "ADR_126_STAGE60_FREEZE.md" in roadmap
    assert "Stage 60 exit" in roadmap

    pr = (ROOT / "PRODUCTION_READINESS.md").read_text(encoding="utf-8")
    assert "STAGE_60_EXIT_CRITERIA.md" in pr or "ADR-126" in pr or "ADR_126" in pr

    sec = (ROOT / "docs" / "SECURITY_GUIDE.md").read_text(encoding="utf-8")
    assert "ADR-126" in sec or "ADR_126" in sec or "test_stage60_exit_h60x.py" in sec
    assert "STAGE_60_EXIT_CRITERIA.md" in sec or "H60x" in sec or "Stage 60 exit" in sec
