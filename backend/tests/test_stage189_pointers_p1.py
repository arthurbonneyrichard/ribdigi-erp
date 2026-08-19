"""Stage 189 P1 — live-training pack pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "live-training-pack-pointers.json"


def test_live_training_pack_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 189 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["live_training_claimed"] is False
    assert data["training_complete_claimed"] is False
    for topic in (
        "knowledge_transfer_stage33",
        "customer_training_cert_stage48",
        "knowledge_base_stage171",
        "cashier_materials_stages172_175",
        "support_sla_remaining_gate_stage188",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "lp-training-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_live_training_pack_pointers_doc_p1():
    doc = (ROOT / "docs/LIVE_TRAINING_PACK_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "KNOWLEDGE_TRANSFER_MVP.md" in doc
    assert "CUSTOMER_TRAINING_CERT_MVP.md" in doc
    assert "KNOWLEDGE_BASE_MVP.md" in doc
    assert "live_training_claimed" in doc
