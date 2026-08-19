"""Stage 86 open — ADR-178 + STAGE_86_PLAN + ADR-177 amendment."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"


@pytest.mark.parametrize(
    "rel",
    [
        "docs/ADR_178_STAGE86_OPEN.md",
        "docs/STAGE_86_PLAN.md",
        "docs/ADR_177_STAGE85_FREEZE.md",
    ],
)
def test_stage86_open_artifacts_exist(rel: str) -> None:
    assert (ROOT / rel).is_file(), f"missing {rel}"


def test_adr178_opens_stage86() -> None:
    text = (DOCS / "ADR_178_STAGE86_OPEN.md").read_text(encoding="utf-8")
    assert "ADR-178" in text and "Stage 86" in text
    assert "House Tenant Provision" in text
    assert "Platform Email Password Reset" in text
    assert "Platform Audit Activity Depth" in text
    assert "House Provision & Platform Access Ops" in text
    assert "user_store_membership_claimed" in text or "ADR-005" in text
    assert "go_live_claimed" in text and "ADR-177" in text
    assert "P1" in text and "E1" in text and "A1" in text and "D1" in text and "H86x" in text


def test_stage86_plan_structure() -> None:
    text = (DOCS / "STAGE_86_PLAN.md").read_text(encoding="utf-8")
    assert "Stage 86" in text
    assert "P1" in text and "E1" in text and "A1" in text and "D1" in text and "H86x" in text
    assert "House Tenant Provision" in text
    assert (
        "Status:** Open" in text
        or "Status: Open" in text
        or "Closed" in text
        or "exit met" in text.lower()
    )


def test_adr177_amended_for_stage86() -> None:
    text = (DOCS / "ADR_177_STAGE85_FREEZE.md").read_text(encoding="utf-8")
    assert "Stage 86 opened" in text or "ADR_178" in text
    assert "ADR_178_STAGE86_OPEN" in text


def test_stage86_listed_in_launch_and_roadmap() -> None:
    launch = (DOCS / "LAUNCH_CHECKLIST.md").read_text(encoding="utf-8")
    assert "STAGE_86_PLAN.md" in launch
    assert "ADR-178" in launch or "ADR_178" in launch
    assert "test_stage86_open.py" in launch
    roadmap = (DOCS / "DEVELOPMENT_ROADMAP.md").read_text(encoding="utf-8")
    assert "ADR_178_STAGE86_OPEN.md" in roadmap and "STAGE_86_PLAN.md" in roadmap
    assert "Stage 86 open" in roadmap
    security = (DOCS / "SECURITY_GUIDE.md").read_text(encoding="utf-8")
    assert "Stage 86 open" in security
    assert "ADR-178" in security or "ADR_178" in security
