"""Users custom-role manage status filter (BR-3.2 soft-lifecycle FE)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_custom_role_manage_status_filter_ui_and_docs():
    page = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert "roleManageFilter" in page
    assert "managedCustomRoles" in page
    assert 'aria-label="Custom role status filter"' in page
    assert 'value="all"' in page
    assert 'value="active"' in page
    assert 'value="inactive"' in page
    assert "All statuses" in page
    assert "Active only" in page
    assert "Inactive only" in page
    assert "No custom roles for this filter" in page
    # Assignment pickers stay active-only (except current)
    assert "isRoleActive" in page
    assert "assignableRoles" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "roleManageFilter" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "roleManageFilter" in docs or "Custom role status filter" in docs
