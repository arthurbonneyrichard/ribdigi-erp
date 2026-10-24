"""Sidebar open-feature performance: prefetch JS + reuse warmed GETs."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"


def test_sidebar_enables_next_link_prefetch_and_warms_desk_gets():
    shell = (FRONTEND / "components/Shell.tsx").read_text(encoding="utf-8")
    prefetch = (FRONTEND / "lib/navPrefetch.ts").read_text(encoding="utf-8")
    cache = (FRONTEND / "lib/prefetchCache.ts").read_text(encoding="utf-8")

    assert "prefetch={false}" not in shell
    assert "prefetchPathsForHref" in shell
    assert "router.prefetch" in shell
    assert "warmDestination" in shell
    assert "createPaintGet" in cache
    assert "TTL_MS = 45_000" in cache
    assert "'/sales/invoices'" in prefetch
    assert "'/purchasing/orders'" in prefetch
    assert "'/credit/aging?kind=receivable'" in prefetch


def test_heavy_desks_reuse_prefetched_gets_on_first_paint():
    sales = (FRONTEND / "app/(dashboard)/sales/page.tsx").read_text(encoding="utf-8")
    purchasing = (FRONTEND / "app/(dashboard)/purchasing/page.tsx").read_text(encoding="utf-8")
    customers = (FRONTEND / "app/(dashboard)/customers/page.tsx").read_text(encoding="utf-8")
    credit = (FRONTEND / "app/(dashboard)/credit/page.tsx").read_text(encoding="utf-8")
    expenses = (FRONTEND / "app/(dashboard)/expenses/page.tsx").read_text(encoding="utf-8")
    accounting = (FRONTEND / "app/(dashboard)/accounting/page.tsx").read_text(encoding="utf-8")

    for text in (sales, purchasing, customers, credit, expenses, accounting):
        assert "createPaintGet" in text
        assert "paintGet.get" in text or "paintGet" in text and ".get(" in text

    assert "peekPrefetch('/sales/invoices')" in sales
    assert "`/credit/aging?kind=${startKind}`" in credit


def test_heavy_desks_have_route_loading_skeletons():
    desks = (
        "sales",
        "customers",
        "purchasing",
        "accounting",
        "credit",
        "reports",
        "expenses",
        "ecommerce",
        "stores",
        "company",
        "users",
        "inventory",
        "pos",
    )
    for name in desks:
        path = FRONTEND / "app/(dashboard)" / name / "loading.tsx"
        text = path.read_text(encoding="utf-8")
        assert "PageSkeleton" in text, name
