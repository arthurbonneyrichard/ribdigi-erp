"""Stage 165 K1 — IndexedDB offline queue client + device bind + SW honesty."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_offline_queue_module_k1():
    lib = (ROOT / "frontend/lib/offlineQueue.ts").read_text(encoding="utf-8")
    assert "Stage 165" in lib or "IndexedDB" in lib
    assert "enqueueOfflineOp" in lib
    assert "flushOfflineQueue" in lib
    assert "/sync/push" in lib
    assert "offline_device_id" in lib
    assert "indexedDB" in lib


def test_pos_and_settings_wire_queue_k1():
    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert "enqueueOfflineOp" in pos
    assert "flushOfflineQueue" in pos
    assert "navigator.onLine" in pos
    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert "Bind browser" in company
    assert "offline_device_id" in company


def test_sw_still_never_caches_api_k1():
    sw = (ROOT / "frontend/public/sw.js").read_text(encoding="utf-8")
    assert "isApiOrAuth" in sw or "/api/" in sw
    assert "never" in sw.lower() or "Network-only" in sw
