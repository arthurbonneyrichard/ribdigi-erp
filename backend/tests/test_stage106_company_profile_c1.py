"""Stage 106 C1 — Company profile & departments discoverability."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_company_profile_leaves_c1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/company#logo" in shell
    assert "/company#profile" in shell
    assert "/company#locale" in shell
    assert "/company#departments" in shell
    assert "Company Profile" in shell
    assert "Company Logo" in shell
    assert "Locale Formats" in shell
    assert "Departments" in shell


def test_company_page_profile_anchors_c1():
    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'id="logo"' in company
    assert 'id="profile"' in company
    assert 'id="locale"' in company
    assert 'id="departments"' in company
    assert "scrollIntoView" in company
