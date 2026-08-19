"""Stage 189 B1 — live-training blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "live-training-blockers.json"


def test_live_training_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 189 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_training_claimed"] is False
    assert data["training_complete_claimed"] is False
    assert data["training_certification_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_training_execution"] == "REMAINING"
    assert blockers["training_attendance_certification"] == "REMAINING"
    assert blockers["customer_training_delivery"] == "REMAINING"
    assert blockers["stage33_t1_as_live_training"] == "NON_CLAIM"
    assert blockers["stage48_t1_as_live_training"] == "NON_CLAIM"
    assert blockers["live_training_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "lb-training-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_live_training_blockers_doc_b1():
    doc = (ROOT / "docs/LIVE_TRAINING_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "live_training_claimed" in doc
    assert "Stage 33" in doc
    assert "Stage 48" in doc
    assert "attendance" in doc.lower() or "certification" in doc.lower()
