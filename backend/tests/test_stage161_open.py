"""Stage 161 open — ADR-328 + STAGE_161_PLAN + ADR-327 amendment."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"


@pytest.mark.parametrize(
    "rel",
    [
        "docs/ADR_328_STAGE161_OPEN.md",
        "docs/STAGE_161_PLAN.md",
        "docs/ADR_327_STAGE160_FREEZE.md",
    ],
)
def test_stage161_open_artifacts_exist(rel: str) -> None:
    assert (ROOT / rel).is_file(), f"missing {rel}"


def test_adr328_opens_stage161() -> None:
    text = (DOCS / "ADR_328_STAGE161_OPEN.md").read_text(encoding="utf-8")
    assert "ADR-328" in text and "Stage 161" in text
    assert "profit-loss" in text.lower()
    assert "trial-balance" in text.lower()
    assert "tax" in text.lower()
    assert "ADR-327" in text
    assert "L1" in text and "B1" in text and "X1" in text and "D1" in text and "H161x" in text


def test_stage161_plan_structure() -> None:
    text = (DOCS / "STAGE_161_PLAN.md").read_text(encoding="utf-8")
    assert "Stage 161" in text
    assert "L1" in text and "B1" in text and "X1" in text and "D1" in text and "H161x" in text


def test_adr327_amended_for_stage161() -> None:
    text = (DOCS / "ADR_327_STAGE160_FREEZE.md").read_text(encoding="utf-8")
    assert "Stage 161" in text
    assert "ADR-328" in text or "ADR-329" in text
