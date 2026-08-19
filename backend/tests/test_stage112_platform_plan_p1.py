"""Stage 112 P1 — PlatformShell plan_code leaves + At-risk #at-risk-queue."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_platform_shell_plan_code_and_at_risk_hash_p1():
    shell = (ROOT / "frontend/components/PlatformShell.tsx").read_text(encoding="utf-8")
    assert "plan_code=trial" in shell
    assert "plan_code=starter" in shell
    assert "plan_code=growth" in shell
    assert "plan_code=enterprise" in shell
    assert "focus=at-risk#at-risk-queue" in shell
    assert "Trial Plan Tenants" in shell
    assert "Enterprise Plan Tenants" in shell


def test_platform_tenants_plan_and_at_risk_p1():
    tenants = (ROOT / "frontend/app/platform/tenants/page.tsx").read_text(encoding="utf-8")
    assert "plan_code" in tenants
    assert 'id="at-risk-queue"' in tenants
    assert "Stage 112" in tenants
    assert "scrollIntoView" in tenants
