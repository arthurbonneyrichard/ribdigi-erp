"""Stage 103 C1 — Company org & numbering discoverability."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_company_org_deeplinks_c1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/company#branches" in shell
    assert "/company#document-numbering" in shell
    assert "/company#media" in shell
    assert "Branches" in shell
    assert "Document numbering" in shell
    assert "Media storage" in shell


def test_company_page_org_anchors_c1():
    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'id="branches"' in company
    assert 'id="document-numbering"' in company
    assert 'id="media"' in company
    assert "scrollIntoView" in company
