"""Stage 95 P1 — Party & stock discoverability."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_party_stock_deep_links_p1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/sales?tab=customers" in shell
    assert "/purchasing?tab=suppliers" in shell
    assert "/inventory?tab=stock" in shell
    assert "/inventory?tab=lowstock" in shell
    assert "/stores#warehouses" in shell
    assert "canReadAnyModule" in shell or "customers" in shell

    rbac_fe = (ROOT / "frontend/lib/rbac.ts").read_text(encoding="utf-8")
    assert "canReadAnyModule" in rbac_fe

    tab_q = (ROOT / "frontend/lib/tabQuery.ts").read_text(encoding="utf-8")
    assert "replaceState" in tab_q
    assert "searchParams.set('tab'" in tab_q or 'searchParams.set("tab"' in tab_q

    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'id="warehouses"' in stores
