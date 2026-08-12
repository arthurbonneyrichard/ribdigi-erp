"""Stage 104 R1 — Credit section & admin roles discoverability."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_credit_roles_deeplinks_r1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/credit#aging" in shell
    assert "/credit#early-pay" in shell
    assert "/credit#exchange-rates" in shell
    assert "/credit?kind=payable#payment-schedule" in shell
    assert "/admin/roles#custom" in shell
    assert "/admin/roles#system" in shell
    assert "Custom Roles" in shell
    assert "Credit Aging" in shell


def test_credit_roles_page_anchors_r1():
    credit = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert 'id="aging"' in credit
    assert 'id="early-pay"' in credit
    assert 'id="exchange-rates"' in credit
    assert 'id="payment-schedule"' in credit
    assert "scrollIntoView" in credit

    roles = (ROOT / "frontend/app/admin/roles/page.tsx").read_text(encoding="utf-8")
    assert 'id="custom"' in roles
    assert 'id="system"' in roles
    assert "scrollIntoView" in roles


def test_dashboard_custom_roles_kpi_target_r1():
    api = (ROOT / "backend/app/api.py").read_text(encoding="utf-8")
    assert '"custom_roles": "/admin/roles#custom"' in api
    dash = (ROOT / "frontend/app/dashboard/page.tsx").read_text(encoding="utf-8")
    assert "links.custom_roles" in dash or "/admin/roles#custom" in dash
