"""Stage 171 F1 — FAQ offline/POS/Hold packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "faq-offline-pos.json"


def test_faq_offline_pos_register_f1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 171 and data["pack"] == "F1"
    assert data["packaging_complete"] is True
    assert data["offline_complete_claimed"] is False
    assert data["hosted_kb_saas_claimed"] is False
    assert data["go_live_claimed"] is False
    assert data["attestation_claimed"] is False
    for topic in (
        "offline_sale_queue",
        "hold_soft_reserve",
        "offline_catalog_ttl",
        "conflict_accept_client",
        "device_revoke_pending_queue",
        "backup_drill_link",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "faq-offline-complete-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_faq_offline_pos_doc_f1():
    doc = (ROOT / "docs/FAQ_OFFLINE_POS_MVP.md").read_text(encoding="utf-8")
    assert "offline_complete_claimed" in doc
    assert "Hold" in doc or "soft-reserve" in doc
    assert "BACKUP_RESTORE_DRILL_HONESTY_MVP.md" in doc
    assert "Offline Complete" in doc
