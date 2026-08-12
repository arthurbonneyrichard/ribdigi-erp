"""Stage 106 open — ADR-218 + STAGE_106_PLAN + ADR-217 amendment."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"


@pytest.mark.parametrize(
    "rel",
    [
        "docs/ADR_218_STAGE106_OPEN.md",
        "docs/STAGE_106_PLAN.md",
        "docs/ADR_217_STAGE105_FREEZE.md",
    ],
)
def test_stage106_open_artifacts_exist(rel: str) -> None:
    assert (ROOT / rel).is_file(), f"missing {rel}"


def test_adr218_opens_stage106() -> None:
    text = (DOCS / "ADR_218_STAGE106_OPEN.md").read_text(encoding="utf-8")
    assert "ADR-218" in text and "Stage 106" in text
    assert "Expense" in text or "Purchase" in text
    assert "Company" in text or "Profile" in text
    assert "Notification" in text
    assert "ADR-217" in text
    assert "E1" in text and "C1" in text and "N1" in text and "D1" in text and "H106x" in text


def test_stage106_plan_structure() -> None:
    text = (DOCS / "STAGE_106_PLAN.md").read_text(encoding="utf-8")
    assert "Stage 106" in text
    assert "E1" in text and "C1" in text and "N1" in text and "D1" in text and "H106x" in text
    assert "Closed" in text or "exit met" in text.lower() or "Status:** Open" in text


def test_adr217_amended_for_stage106() -> None:
    text = (DOCS / "ADR_217_STAGE105_FREEZE.md").read_text(encoding="utf-8")
    assert "Stage 106 opened" in text or "ADR_218" in text
    assert "ADR_218_STAGE106_OPEN" in text


def test_stage106_listed_in_launch_and_roadmap() -> None:
    launch = (DOCS / "LAUNCH_CHECKLIST.md").read_text(encoding="utf-8")
    assert "STAGE_106_PLAN.md" in launch
    assert "ADR-218" in launch or "ADR_218" in launch
    assert "test_stage106_open.py" in launch
    roadmap = (DOCS / "DEVELOPMENT_ROADMAP.md").read_text(encoding="utf-8")
    assert "ADR_218_STAGE106_OPEN.md" in roadmap and "STAGE_106_PLAN.md" in roadmap
    assert "Stage 106 open" in roadmap
    security = (DOCS / "SECURITY_GUIDE.md").read_text(encoding="utf-8")
    assert "Stage 106 open" in security
    assert "ADR-218" in security or "ADR_218" in security
