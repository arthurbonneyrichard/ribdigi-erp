"""Stage 391 P1 — offline device auth token pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "offline-device-auth-token-pack-rg-pointers.json"


def test_offline_device_auth_token_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 391 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["offline_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "change_impact_section8_offline_device_auth_token",
        "offline_catalog_snapshot_pack_remaining_gate_stage390",
        "offline_client_request_id_pack_remaining_gate_stage389",
        "device_offline_registry_pack_remaining_gate_stage374",
        "offline_complete_pack_remaining_gate_stage329",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "odatprp-checklist-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_offline_device_auth_token_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/OFFLINE_DEVICE_AUTH_TOKEN_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "CHANGE_IMPACT_MVP_UPDATE_2026-08-14.md" in doc
    assert "OFFLINE_CATALOG_SNAPSHOT_PACK_REMAINING_GATE_MVP.md" in doc
    assert "OFFLINE_CLIENT_REQUEST_ID_PACK_REMAINING_GATE_MVP.md" in doc
    assert "DEVICE_OFFLINE_REGISTRY_PACK_REMAINING_GATE_MVP.md" in doc
    assert "OFFLINE_COMPLETE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "offline_complete_claimed" in doc
    assert "offline_device_auth_token_complete_claimed" in doc
