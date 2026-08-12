"""Stage 138 open — ADR-282 + STAGE_138_PLAN + ADR-281 amendment."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"


@pytest.mark.parametrize(
    "rel",
    [
        "docs/ADR_282_STAGE138_OPEN.md",
        "docs/STAGE_138_PLAN.md",
        "docs/ADR_281_STAGE137_FREEZE.md",
    ],
)
def test_stage138_open_artifacts_exist(rel: str) -> None:
    assert (ROOT / rel).is_file(), f"missing {rel}"


def test_adr282_opens_stage138() -> None:
    text = (DOCS / "ADR_282_STAGE138_OPEN.md").read_text(encoding="utf-8")
    assert "ADR-282" in text and "Stage 138" in text
    assert "early-pay" in text.lower() or "early pay" in text.lower()
    assert "expense" in text.lower()
    assert "purchasing" in text.lower()
    assert "ADR-281" in text
    assert "C1" in text and "E1" in text and "P1" in text and "D1" in text and "H138x" in text


def test_stage138_plan_structure() -> None:
    text = (DOCS / "STAGE_138_PLAN.md").read_text(encoding="utf-8")
    assert "Stage 138" in text
    assert "C1" in text and "E1" in text and "P1" in text and "D1" in text and "H138x" in text


def test_adr281_amended_for_stage138() -> None:
    text = (DOCS / "ADR_281_STAGE137_FREEZE.md").read_text(encoding="utf-8")
    assert "Stage 138" in text
    assert "ADR-282" in text or "ADR-283" in text
