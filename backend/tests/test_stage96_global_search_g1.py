"""Stage 96 G1 — Global topbar search."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_global_search_products_and_customers_g1(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    empty = await ac.get("/api/v1/search?q=", headers=headers)
    assert empty.status_code == 200, empty.text
    assert empty.json()["data"]["results"] == []

    # Seed customer name from conftest is typically present; also search products.
    r = await ac.get("/api/v1/search?q=a", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert "results" in body
    for hit in body["results"]:
        assert hit.get("href")
        assert hit.get("kind") in {"product", "customer"}
        assert hit.get("label")


def test_shell_search_ui_g1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/search?q=" in shell or "`/search?q=" in shell or "/search?q=${" in shell
    assert "global-search" in shell
    assert "Search products or customers" in shell
    css = (ROOT / "frontend/app/globals.css").read_text(encoding="utf-8")
    assert "global-search" in css
