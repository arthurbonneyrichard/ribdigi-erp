"""Stage 80 open — ADR-166 + STAGE_80_PLAN + ADR-165 amendment."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"


@pytest.mark.parametrize(
    "rel",
    [
        "docs/ADR_166_STAGE80_OPEN.md",
        "docs/STAGE_80_PLAN.md",
        "docs/ADR_165_STAGE79_FREEZE.md",
    ],
)
def test_stage80_open_artifacts_exist(rel: str) -> None:
    assert (ROOT / rel).is_file(), f"missing {rel}"


def test_adr166_opens_stage80() -> None:
    text = (DOCS / "ADR_166_STAGE80_OPEN.md").read_text(encoding="utf-8")
    assert "ADR-166" in text and "Stage 80" in text
    assert "Platform Owner Dashboard Charts" in text
    assert "Tenant Role-Scoped Dashboards" in text
    assert "Dual-Console Dashboard Fidelity" in text
    assert "mrr_fabricated_claimed" in text or "billing_complete_claimed" in text
    assert "go_live_claimed" in text and "ADR-165" in text
    assert "P1" in text and "T1" in text and "D1" in text and "H80x" in text


def test_stage80_plan_structure() -> None:
    text = (DOCS / "STAGE_80_PLAN.md").read_text(encoding="utf-8")
    assert "Stage 80" in text
    assert "P1" in text and "T1" in text and "D1" in text and "H80x" in text
    assert "Platform Owner Dashboard Charts" in text
    assert (
        "Status:** Open" in text
        or "Status: Open" in text
        or "Closed" in text
        or "exit met" in text.lower()
    )


def test_adr165_amended_for_stage80() -> None:
    text = (DOCS / "ADR_165_STAGE79_FREEZE.md").read_text(encoding="utf-8")
    assert "Stage 80 opened" in text or "ADR_166" in text
    assert "ADR_166_STAGE80_OPEN" in text


def test_stage80_listed_in_launch_and_roadmap() -> None:
    launch = (DOCS / "LAUNCH_CHECKLIST.md").read_text(encoding="utf-8")
    assert "STAGE_80_PLAN.md" in launch
    assert "ADR-166" in launch or "ADR_166" in launch
    assert "test_stage80_open.py" in launch
    roadmap = (DOCS / "DEVELOPMENT_ROADMAP.md").read_text(encoding="utf-8")
    assert "ADR_166_STAGE80_OPEN.md" in roadmap and "STAGE_80_PLAN.md" in roadmap
    assert "Stage 80 open" in roadmap
    security = (DOCS / "SECURITY_GUIDE.md").read_text(encoding="utf-8")
    assert "Stage 80 open" in security
    assert "ADR-166" in security or "ADR_166" in security
