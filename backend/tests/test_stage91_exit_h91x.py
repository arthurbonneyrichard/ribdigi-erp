"""Stage 91 H91x — exit criteria + freeze ADR exist."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_stage91_exit_criteria_and_freeze_adr():
    exit_doc = (ROOT / "docs" / "STAGE_91_EXIT_CRITERIA.md").read_text(encoding="utf-8")
    for token in ("I1", "N1", "P1", "D1", "H91x", "COMPLETE", "ADR-189"):
        assert token in exit_doc, token
    assert "Investigation" in exit_doc or "Evidence" in exit_doc or "Operator" in exit_doc
    assert "CRITICAL" in exit_doc or "MISSING" in exit_doc or "Sign-off" in exit_doc

    freeze = (ROOT / "docs" / "ADR_189_STAGE91_FREEZE.md").read_text(encoding="utf-8")
    assert "Stage 91" in freeze
    assert "frozen" in freeze.lower() or "Freeze" in freeze
    assert "Stage 92" in freeze and "Stage 90" in freeze and "Accepted" in freeze
    assert (
        "user_store_membership_claimed" in freeze
        or "billing_complete_claimed" in freeze
        or "subscriptions_live_claimed" in freeze
        or "go_live_claimed" in freeze
    )

    plan = (ROOT / "docs" / "STAGE_91_PLAN.md").read_text(encoding="utf-8")
    assert "Closed" in plan or "exit met" in plan.lower() or "ADR-189" in plan
    for ws in ("I1", "N1", "P1", "D1", "H91x"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws

    assert (ROOT / "docs" / "ADR_188_STAGE91_OPEN.md").is_file()
    assert (ROOT / "docs" / "STAGE_91_FIDELITY.md").is_file()
    assert (ROOT / "docs" / "STAGE_91_EXIT_CRITERIA.md").is_file()
    assert (ROOT / "docs" / "ADR_189_STAGE91_FREEZE.md").is_file()


def test_stage91_exit_listed_in_launch_and_roadmap():
    launch = (ROOT / "docs" / "LAUNCH_CHECKLIST.md").read_text(encoding="utf-8")
    assert "test_stage91_exit_h91x.py" in launch
    assert "ADR-189" in launch or "ADR_189" in launch
    assert "STAGE_91_EXIT_CRITERIA.md" in launch or "H91x" in launch

    roadmap = (ROOT / "docs" / "DEVELOPMENT_ROADMAP.md").read_text(encoding="utf-8")
    assert "STAGE_91_EXIT_CRITERIA.md" in roadmap
    assert "ADR_189_STAGE91_FREEZE.md" in roadmap
    assert "Stage 91 exit" in roadmap

    pr = (ROOT / "PRODUCTION_READINESS.md").read_text(encoding="utf-8")
    assert "STAGE_91_EXIT_CRITERIA.md" in pr or "ADR-189" in pr or "ADR_189" in pr

    sec = (ROOT / "docs" / "SECURITY_GUIDE.md").read_text(encoding="utf-8")
    assert "ADR-189" in sec or "ADR_189" in sec or "test_stage91_exit_h91x.py" in sec
    assert "STAGE_91_EXIT_CRITERIA.md" in sec or "H91x" in sec or "Stage 91 exit" in sec
