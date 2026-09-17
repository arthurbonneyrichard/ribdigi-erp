"""OpenAPI honesty tips #602–#605: Company regional format aria-labels."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_company_regional_format_aria_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Company date format aria OpenAPI",
        "Company decimal separator aria OpenAPI",
        "Company thousand separator aria OpenAPI",
        "Company time format aria OpenAPI",
    ):
        assert title in agents, title
    assert "Company date format" in agents
    assert "Company format OpenAPI" in agents

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Company date format" in docs
    assert "Company decimal separator" in docs
    assert "Company thousand separator" in docs
    assert "Company time format" in docs

    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    for label in (
        "Company date format",
        "Company decimal separator",
        "Company thousand separator",
        "Company time format",
        "Tax filing period",
    ):
        assert f'aria-label="{label}"' in company, label
