"""Stage 136 open — ADR-278 + STAGE_136_PLAN + ADR-277 amendment."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"


@pytest.mark.parametrize(
    "rel",
    [
        "docs/ADR_278_STAGE136_OPEN.md",
        "docs/STAGE_136_PLAN.md",
        "docs/ADR_277_STAGE135_FREEZE.md",
    ],
)
def test_stage136_open_artifacts_exist(rel: str) -> None:
    assert (ROOT / rel).is_file(), f"missing {rel}"


def test_adr278_opens_stage136() -> None:
    text = (DOCS / "ADR_278_STAGE136_OPEN.md").read_text(encoding="utf-8")
    assert "ADR-278" in text and "Stage 136" in text
    assert "customer" in text.lower() and "supplier" in text.lower()
    assert "aging" in text.lower()
    assert "ADR-277" in text
    assert "C1" in text and "S1" in text and "A1" in text and "D1" in text and "H136x" in text


def test_stage136_plan_structure() -> None:
    text = (DOCS / "STAGE_136_PLAN.md").read_text(encoding="utf-8")
    assert "Stage 136" in text
    assert "C1" in text and "S1" in text and "A1" in text and "D1" in text and "H136x" in text


def test_adr277_amended_for_stage136() -> None:
    text = (DOCS / "ADR_277_STAGE135_FREEZE.md").read_text(encoding="utf-8")
    assert "Stage 136" in text
    assert "ADR-278" in text or "ADR-279" in text
