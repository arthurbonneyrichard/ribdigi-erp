"""Stage 163 P1 — PWA manifest + static-only service worker."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_pwa_manifest_and_icons_p1():
    manifest = (ROOT / "frontend/public/manifest.webmanifest").read_text(encoding="utf-8")
    assert "RIBDIGI" in manifest
    assert "standalone" in manifest
    assert "icon-192.png" in manifest
    assert "icon-512.png" in manifest
    assert (ROOT / "frontend/public/icon-192.png").is_file()
    assert (ROOT / "frontend/public/icon-512.png").is_file()


def test_service_worker_static_only_p1():
    sw = (ROOT / "frontend/public/sw.js").read_text(encoding="utf-8")
    assert "Stage 163" in sw or "static" in sw.lower()
    assert "/api/v1" in sw or "/api/" in sw
    assert "never" in sw.lower() or "Network-only" in sw or "isApiOrAuth" in sw
    assert "caches" in sw
    # Must not instruct caching API responses into Cache Storage for /api/
    assert "cache.put" in sw
    assert "isApiOrAuth" in sw


def test_layout_registers_sw_and_manifest_p1():
    layout = (ROOT / "frontend/app/layout.tsx").read_text(encoding="utf-8")
    assert "manifest.webmanifest" in layout or "manifest:" in layout
    assert "ServiceWorkerRegister" in layout
    reg = (ROOT / "frontend/components/ServiceWorkerRegister.tsx").read_text(encoding="utf-8")
    assert "/sw.js" in reg
    assert "serviceWorker" in reg
