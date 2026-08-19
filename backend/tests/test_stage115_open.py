"""Stage 115 open — ADR-236 + STAGE_115_PLAN + ADR-235 amendment."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"


@pytest.mark.parametrize(
    "rel",
    [
        "docs/ADR_236_STAGE115_OPEN.md",
        "docs/STAGE_115_PLAN.md",
        "docs/ADR_235_STAGE114_FREEZE.md",
    ],
)
def test_stage115_open_artifacts_exist(rel: str) -> None:
    assert (ROOT / rel).is_file(), f"missing {rel}"


def test_adr236_opens_stage115() -> None:
    text = (DOCS / "ADR_236_STAGE115_OPEN.md").read_text(encoding="utf-8")
    assert "ADR-236" in text and "Stage 115" in text
    assert "History" in text or "Notification" in text
    assert "Purchase" in text or "invoice" in text
    assert "Draft" in text or "Platform" in text or "role" in text
    assert "ADR-235" in text
    assert "N1" in text and "P1" in text and "O1" in text and "D1" in text and "H115x" in text


def test_stage115_plan_structure() -> None:
    text = (DOCS / "STAGE_115_PLAN.md").read_text(encoding="utf-8")
    assert "Stage 115" in text
    assert "N1" in text and "P1" in text and "O1" in text and "D1" in text and "H115x" in text
    assert "Closed" in text or "exit met" in text.lower() or "Status:** Open" in text


def test_adr235_amended_for_stage115() -> None:
    text = (DOCS / "ADR_235_STAGE114_FREEZE.md").read_text(encoding="utf-8")
    assert "Stage 115 opened" in text or "ADR_236" in text
    assert "ADR_236_STAGE115_OPEN" in text


def test_stage115_listed_in_launch_and_roadmap() -> None:
    launch = (DOCS / "LAUNCH_CHECKLIST.md").read_text(encoding="utf-8")
    assert "STAGE_115_PLAN.md" in launch
    assert "ADR-236" in launch or "ADR_236" in launch
    assert "test_stage115_open.py" in launch
    roadmap = (DOCS / "DEVELOPMENT_ROADMAP.md").read_text(encoding="utf-8")
    assert "ADR_236_STAGE115_OPEN.md" in roadmap and "STAGE_115_PLAN.md" in roadmap
    assert "Stage 115 open" in roadmap
    security = (DOCS / "SECURITY_GUIDE.md").read_text(encoding="utf-8")
    assert "Stage 115 open" in security
    assert "ADR-236" in security or "ADR_236" in security
