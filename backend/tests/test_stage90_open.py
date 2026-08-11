"""Stage 90 open — ADR-186 + STAGE_90_PLAN + ADR-185 amendment."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"


@pytest.mark.parametrize(
    "rel",
    [
        "docs/ADR_186_STAGE90_OPEN.md",
        "docs/STAGE_90_PLAN.md",
        "docs/ADR_185_STAGE89_FREEZE.md",
    ],
)
def test_stage90_open_artifacts_exist(rel: str) -> None:
    assert (ROOT / rel).is_file(), f"missing {rel}"


def test_adr186_opens_stage90() -> None:
    text = (DOCS / "ADR_186_STAGE90_OPEN.md").read_text(encoding="utf-8")
    assert "ADR-186" in text and "Stage 90" in text
    assert "Email Delivery" in text
    assert "Operator Contact" in text or "Runbook" in text
    assert "Findability" in text or "Plan Context" in text
    assert "House Operator Visibility & Delivery Ops" in text
    assert "user_store_membership_claimed" in text or "ADR-005" in text
    assert "go_live_claimed" in text and "ADR-185" in text
    assert "E1" in text and "O1" in text and "Q1" in text and "D1" in text and "H90x" in text


def test_stage90_plan_structure() -> None:
    text = (DOCS / "STAGE_90_PLAN.md").read_text(encoding="utf-8")
    assert "Stage 90" in text
    assert "E1" in text and "O1" in text and "Q1" in text and "D1" in text and "H90x" in text
    assert "Email Delivery" in text
    assert (
        "Status:** Open" in text
        or "Status: Open" in text
        or "Closed" in text
        or "exit met" in text.lower()
    )


def test_adr185_amended_for_stage90() -> None:
    text = (DOCS / "ADR_185_STAGE89_FREEZE.md").read_text(encoding="utf-8")
    assert "Stage 90 opened" in text or "ADR_186" in text
    assert "ADR_186_STAGE90_OPEN" in text


def test_stage90_listed_in_launch_and_roadmap() -> None:
    launch = (DOCS / "LAUNCH_CHECKLIST.md").read_text(encoding="utf-8")
    assert "STAGE_90_PLAN.md" in launch
    assert "ADR-186" in launch or "ADR_186" in launch
    assert "test_stage90_open.py" in launch
    roadmap = (DOCS / "DEVELOPMENT_ROADMAP.md").read_text(encoding="utf-8")
    assert "ADR_186_STAGE90_OPEN.md" in roadmap and "STAGE_90_PLAN.md" in roadmap
    assert "Stage 90 open" in roadmap
    security = (DOCS / "SECURITY_GUIDE.md").read_text(encoding="utf-8")
    assert "Stage 90 open" in security
    assert "ADR-186" in security or "ADR_186" in security
