"""Stage 174 T1 — conflict triage + catalog age + backup pointer packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "store-close-triage.json"


def test_store_close_triage_register_t1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 174 and data["pack"] == "T1"
    assert data["packaging_complete"] is True
    assert data["offline_complete_claimed"] is False
    assert data["live_dr_claimed"] is False
    assert data["go_live_claimed"] is False
    assert data["attestation_claimed"] is False
    assert data["catalog_ttl_hours"] == 4
    for topic in ("conflict_triage", "offline_catalog_age", "backup_drill_pointer"):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "st-offline-dr-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_store_close_triage_doc_t1():
    doc = (ROOT / "docs/STORE_CLOSE_TRIAGE_MVP.md").read_text(encoding="utf-8")
    assert "Accept client" in doc or "conflict" in doc.lower()
    assert "BACKUP_RESTORE_DRILL_HONESTY_MVP.md" in doc
    assert "4 hour" in doc or "4h" in doc or "TTL" in doc
    assert "live_dr_claimed" in doc
    assert "offline_complete_claimed" in doc
