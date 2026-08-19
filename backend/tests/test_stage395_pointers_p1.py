"""Stage 395 P1 — offline SYNC ERROR surface pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "offline-sync-error-surface-pack-rg-pointers.json"


def test_offline_sync_error_surface_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 395 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["offline_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "change_impact_section4_offline_sync_error_surface",
        "offline_queue_depth_metrics_pack_remaining_gate_stage394",
        "offline_settings_sync_ia_pack_remaining_gate_stage393",
        "offline_connectivity_badge_pack_remaining_gate_stage392",
        "offline_complete_pack_remaining_gate_stage329",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "osesprp-checklist-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_offline_sync_error_surface_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/OFFLINE_SYNC_ERROR_SURFACE_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "CHANGE_IMPACT_MVP_UPDATE_2026-08-14.md" in doc
    assert "OFFLINE_QUEUE_DEPTH_METRICS_PACK_REMAINING_GATE_MVP.md" in doc
    assert "OFFLINE_SETTINGS_SYNC_IA_PACK_REMAINING_GATE_MVP.md" in doc
    assert "OFFLINE_CONNECTIVITY_BADGE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "OFFLINE_COMPLETE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "offline_complete_claimed" in doc
    assert "offline_sync_error_surface_complete_claimed" in doc
