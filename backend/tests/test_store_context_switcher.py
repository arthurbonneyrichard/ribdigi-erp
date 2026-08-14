"""Global store context switcher FE packaging (Phase 4 multi-store UX)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_store_context_switcher_packaged():
    ctx = (ROOT / "frontend/lib/storeContext.tsx").read_text(encoding="utf-8")
    assert "StoreProvider" in ctx
    assert "ribdigi.activeStoreId" in ctx
    assert "setStoreId" in ctx

    switcher = (ROOT / "frontend/components/StoreSwitcher.tsx").read_text(encoding="utf-8")
    assert "store-context-switcher" in switcher
    assert "All stores" in switcher

    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "StoreProvider" in shell
    assert "StoreSwitcher" in shell

    for rel in (
        "frontend/app/pos/page.tsx",
        "frontend/app/sales/page.tsx",
        "frontend/app/reports/page.tsx",
        "frontend/app/tax/page.tsx",
        "frontend/app/expenses/page.tsx",
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "useStoreContext" in text, rel
        assert "setCtxStoreId" in text, rel

    roadmap = (ROOT / "docs/DEVELOPMENT_ROADMAP.md").read_text(encoding="utf-8")
    assert "Shell `StoreSwitcher`" in roadmap or "Shell StoreSwitcher" in roadmap
