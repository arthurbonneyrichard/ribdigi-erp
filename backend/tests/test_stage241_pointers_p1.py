"""Stage 241 P1 — live training pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "live-training-pack-rg-pointers.json"


def test_live_training_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 241 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["live_training_claimed"] is False
    assert data["training_complete_claimed"] is False
    for topic in (
        "customer_training_cert_stage48_t1",
        "live_training_remaining_gate_stage189",
        "knowledge_transfer_pack_remaining_gate_stage240",
        "operator_handoff_pack_remaining_gate_stage239",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ltprp-training-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_live_training_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/LIVE_TRAINING_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "CUSTOMER_TRAINING_CERT_MVP.md" in doc
    assert "LIVE_TRAINING_REMAINING_GATE_MVP.md" in doc
    assert "KNOWLEDGE_TRANSFER_PACK_REMAINING_GATE_MVP.md" in doc
    assert "live_training_claimed" in doc
