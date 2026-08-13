"""Stage 216 B1 — knowledge transfer blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "knowledge-transfer-blockers.json"


def test_knowledge_transfer_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 216 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_knowledge_transfer_claimed"] is False
    assert data["live_training_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_operator_admin_training_delivery"] == "REMAINING"
    assert blockers["training_attendance_certification"] == "REMAINING"
    assert blockers["stage33_t1_as_live_training"] == "NON_CLAIM"
    assert blockers["live_training_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ktb-training-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_knowledge_transfer_blockers_doc_b1():
    doc = (ROOT / "docs/KNOWLEDGE_TRANSFER_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "live_training_claimed" in doc
    assert "Stage 33" in doc
