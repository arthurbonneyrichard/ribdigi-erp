"""Stage 169 R1 — offline/sync operator runbook packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "offline-sync-runbook.json"


def test_offline_sync_runbook_register_r1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 169
    assert data["pack"] == "R1"
    assert data["packaging_complete"] is True
    assert data["offline_complete_claimed"] is False
    assert data["attestation_claimed"] is False
    for proc in (
        "register_bind_device",
        "offline_pos_sale_flush",
        "offline_catalog_ttl",
        "conflict_resolve",
        "device_revoke_mid_queue",
        "hold_soft_reserve_expiry",
    ):
        assert proc in data["procedures"], proc
    for rel in data["stage_refs"]:
        assert (ROOT / rel).is_file(), rel
    assert (ROOT / data["attestation_doc"]).is_file()
    assert (ROOT / data["attestation_register"]).is_file()


def test_offline_sync_runbook_doc_r1():
    doc = (ROOT / "docs/OFFLINE_SYNC_RUNBOOK_MVP.md").read_text(encoding="utf-8")
    assert "Offline Complete" in doc
    assert "MISSING" in doc or "not claim" in doc.lower()
    assert "/sync/push" in doc or "Flush offline queue" in doc
    assert "Revoke" in doc or "revoke" in doc
    assert "4h" in doc or "TTL" in doc
