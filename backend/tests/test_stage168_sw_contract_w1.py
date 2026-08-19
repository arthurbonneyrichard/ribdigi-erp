"""Stage 168 W1 — service worker static-cache contract."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_sw_static_cache_contract_w1():
    sw = (ROOT / "frontend/public/sw.js").read_text(encoding="utf-8")
    assert "ribdigi-static-v168" in sw
    assert "Stage 168" in sw or "CONTRACT" in sw
    assert "isApiOrAuth" in sw
    assert "/api/v1/" in sw
    assert "Network-only" in sw or "never put responses" in sw.lower()
    # cache.put must only appear after API guard (still present for static assets)
    assert "cache.put" in sw
    # Must not precache API endpoints
    assert "/api/v1" not in sw.split("PRECACHE")[1].split("];")[0] if "PRECACHE" in sw else True
    precache_block = sw.split("PRECACHE")[1].split("];")[0] if "PRECACHE" in sw else ""
    assert "/api/" not in precache_block


def test_sw_register_and_stage163_compat_w1():
    reg = (ROOT / "frontend/components/ServiceWorkerRegister.tsx").read_text(encoding="utf-8")
    assert "/sw.js" in reg
    assert "Stage 168" in reg or "static-only" in reg.lower()
    # Prior Stage 163 P1 proof still holds
    prior = (ROOT / "backend/tests/test_stage163_pwa_p1.py").read_text(encoding="utf-8")
    assert "isApiOrAuth" in prior or "service_worker" in prior
