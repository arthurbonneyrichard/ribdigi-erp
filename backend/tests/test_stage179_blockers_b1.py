"""Stage 179 B1 — Offline Complete blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "offline-complete-blockers.json"


def test_offline_complete_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 179 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["offline_complete_claimed"] is False
    assert data["attestation_claimed"] is False
    assert data["go_live_claimed"] is False
    assert data["browser_e2e_claimed"] is False
    for key in (
        "sw_static_cache_contract",
        "sync_push_pos_sale_flush_path",
        "device_revoke_mid_queue_honesty",
        "offline_queue_no_tokens",
    ):
        assert data["proven"][key] == "COMPLETE", key
    assert data["missing"]["browser_playwright_offline_e2e"] == "MISSING"
    assert data["missing"]["offline_complete_product_claim"] == "MISSING"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ob-offline-complete-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_offline_complete_blockers_doc_b1():
    doc = (ROOT / "docs/OFFLINE_COMPLETE_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "Playwright" in doc or "E2E" in doc
    assert "SW" in doc or "static-cache" in doc
    assert "flush" in doc.lower() or "sync/push" in doc
    assert "revoke" in doc.lower()
    assert "offline_complete_claimed" in doc
