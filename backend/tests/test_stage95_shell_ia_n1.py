"""Stage 95 N1 — Tenant Shell IA regrouping."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_mvp_sections_and_aliases_n1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    for section in ("Commerce", "People", "Finance", "Operations", "User Management"):
        assert section in shell, section
    assert "Settings" in shell and "/company" in shell
    assert "Stores" in shell and "/stores" in shell
    assert "Multi-Store" not in shell
    # Company label removed from primary nav (Settings alias)
    assert "label: 'Company'" not in shell and "['Company'" not in shell
    assert "label: 'Admin'" not in shell

    rbac = (ROOT / "backend/app/rbac.py").read_text(encoding="utf-8")
    assert '"/company": "company"' in rbac or "'/company': 'company'" in rbac
    assert "Settings" in rbac or "MVP Navigation" in rbac
    assert '"/stores": "stores"' in rbac or "'/stores': 'stores'" in rbac
