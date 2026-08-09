"""Stage 1 D11 — menu visibility equals module permission (ADR-004)."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_adr_004_and_shell_use_shared_module_menu_helper():
    adr = (ROOT / "docs" / "ADR_004_MENU_PERMISSIONS.md").read_text(encoding="utf-8")
    assert "Menu visibility = module permission" in adr or "menu visibility = module permission" in adr.lower()
    assert "No separate menu/submenu permission store" in adr

    helper = (ROOT / "frontend" / "lib" / "rbac.ts").read_text(encoding="utf-8")
    assert "export function canReadModule" in helper
    assert "actions.includes('read')" in helper

    shell = (ROOT / "frontend" / "components" / "Shell.tsx").read_text(encoding="utf-8")
    assert "from '../lib/rbac'" in shell
    assert "canReadModule(permissions, module)" in shell
    # Must not redefine a divergent local helper
    assert "function canReadModule(" not in shell
