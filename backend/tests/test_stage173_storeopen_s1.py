"""Stage 173 S1 — store-open checklist hub packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "store-open-checklist.json"


def test_store_open_checklist_register_s1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 173 and data["pack"] == "S1"
    assert data["packaging_complete"] is True
    assert data["offline_complete_claimed"] is False
    assert data["live_training_claimed"] is False
    assert data["go_live_claimed"] is False
    assert data["attestation_claimed"] is False
    assert data["distinct_from_stage172_dayone"] is True
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "so-offline-complete-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_store_open_checklist_doc_s1():
    doc = (ROOT / "docs/STORE_OPEN_CHECKLIST_MVP.md").read_text(encoding="utf-8")
    assert "offline_complete_claimed" in doc
    assert "STORE_OPEN_LOWSTOCK_MVP.md" in doc
    assert "STORE_OPEN_HEALTH_MVP.md" in doc
    assert "Stage 172" in doc
