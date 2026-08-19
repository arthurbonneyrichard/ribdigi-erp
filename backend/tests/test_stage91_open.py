"""Stage 91 open — ADR-188 + STAGE_91_PLAN + ADR-187 amendment."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"


@pytest.mark.parametrize(
    "rel",
    [
        "docs/ADR_188_STAGE91_OPEN.md",
        "docs/STAGE_91_PLAN.md",
        "docs/ADR_187_STAGE90_FREEZE.md",
    ],
)
def test_stage91_open_artifacts_exist(rel: str) -> None:
    assert (ROOT / rel).is_file(), f"missing {rel}"


def test_adr188_opens_stage91() -> None:
    text = (DOCS / "ADR_188_STAGE91_OPEN.md").read_text(encoding="utf-8")
    assert "ADR-188" in text and "Stage 91" in text
    assert "Date-Range" in text or "Investigation" in text
    assert "Deep-Links" in text or "Delivery Context" in text
    assert "Evidence" in text or "Staff Presence" in text
    assert "House Operator Investigation & Evidence Ops" in text
    assert "user_store_membership_claimed" in text or "ADR-005" in text
    assert "go_live_claimed" in text and "ADR-187" in text
    assert "I1" in text and "N1" in text and "P1" in text and "D1" in text and "H91x" in text


def test_stage91_plan_structure() -> None:
    text = (DOCS / "STAGE_91_PLAN.md").read_text(encoding="utf-8")
    assert "Stage 91" in text
    assert "I1" in text and "N1" in text and "P1" in text and "D1" in text and "H91x" in text
    assert "Investigation" in text or "Evidence" in text
    assert (
        "Status:** Open" in text
        or "Status: Open" in text
        or "Closed" in text
        or "exit met" in text.lower()
    )


def test_adr187_amended_for_stage91() -> None:
    text = (DOCS / "ADR_187_STAGE90_FREEZE.md").read_text(encoding="utf-8")
    assert "Stage 91 opened" in text or "ADR_188" in text
    assert "ADR_188_STAGE91_OPEN" in text


def test_stage91_listed_in_launch_and_roadmap() -> None:
    launch = (DOCS / "LAUNCH_CHECKLIST.md").read_text(encoding="utf-8")
    assert "STAGE_91_PLAN.md" in launch
    assert "ADR-188" in launch or "ADR_188" in launch
    assert "test_stage91_open.py" in launch
    roadmap = (DOCS / "DEVELOPMENT_ROADMAP.md").read_text(encoding="utf-8")
    assert "ADR_188_STAGE91_OPEN.md" in roadmap and "STAGE_91_PLAN.md" in roadmap
    assert "Stage 91 open" in roadmap
    security = (DOCS / "SECURITY_GUIDE.md").read_text(encoding="utf-8")
    assert "Stage 91 open" in security
    assert "ADR-188" in security or "ADR_188" in security
