"""Stage 94 T2 — Console state & queue awareness."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_at_risk_badge_and_empty_states_t2():
    shell = (ROOT / "frontend/components/PlatformShell.tsx").read_text(encoding="utf-8")
    assert "/platform/tenants/at-risk" in shell
    assert "within_days=14" in shell
    assert "at-risk" in shell
    assert "atRiskTotal" in shell or "at_risk" in shell

    audit = (ROOT / "frontend/app/platform/audit/page.tsx").read_text(encoding="utf-8")
    assert "No platform audit events yet." in audit
    assert "No platform activity in this window" in audit
    assert "isActivity" in audit

    dash = (ROOT / "frontend/app/platform/dashboard/page.tsx").read_text(encoding="utf-8")
    assert 'href="/platform/plans"' in dash or "href=\"/platform/plans\"" in dash
    assert "Plan distribution" in dash
