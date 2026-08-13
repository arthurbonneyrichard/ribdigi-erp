"""Stage 172 O1 — POS day-one Hold/flush/accept-client packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "cashier-pos-dayone.json"


def test_cashier_pos_dayone_register_o1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 172 and data["pack"] == "O1"
    assert data["packaging_complete"] is True
    assert data["offline_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    assert data["attestation_claimed"] is False
    for topic in ("hold_soft_reserve", "sync_flush", "accept_client"):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "po-offline-complete-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_cashier_pos_dayone_doc_o1():
    doc = (ROOT / "docs/CASHIER_POS_DAYONE_MVP.md").read_text(encoding="utf-8")
    assert "Hold" in doc
    assert "sync/push" in doc or "/sync/push" in doc
    assert "Accept client" in doc or "accept client" in doc.lower()
    assert "OFFLINE_SYNC_ESCALATION_MVP.md" in doc
    assert "offline_complete_claimed" in doc
