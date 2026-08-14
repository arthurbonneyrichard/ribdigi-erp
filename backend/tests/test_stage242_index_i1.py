"""Stage 242 I1 — customer training cert pack remaining-gate index hub packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "customer-training-cert-pack-remaining-gate.json"


def test_customer_training_cert_pack_remaining_gate_register_i1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 242 and data["pack"] == "I1"
    assert data["packaging_complete"] is True
    assert data["live_training_claimed"] is False
    assert data["training_complete_claimed"] is False
    assert data["training_certification_claimed"] is False
    assert data["go_live_claimed"] is False
    assert data["distinct_from_stage48_t1_customer_training_cert"] is True
    assert data["distinct_from_stage241_live_training_pack_remaining_gate"] is True
    assert data["distinct_from_stage189_live_training_remaining_gate"] is True
    assert data["distinct_from_stage240_knowledge_transfer_pack_remaining_gate"] is True
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ctcpr-training-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_customer_training_cert_pack_remaining_gate_doc_i1():
    doc = (ROOT / "docs/CUSTOMER_TRAINING_CERT_PACK_REMAINING_GATE_MVP.md").read_text(
        encoding="utf-8"
    )
    assert "live_training_claimed" in doc
    assert "training_certification_claimed" in doc
    assert "CUSTOMER_TRAINING_CERT_PACK_RG_BLOCKERS_MVP.md" in doc
    assert "CUSTOMER_TRAINING_CERT_PACK_RG_POINTERS_MVP.md" in doc
    assert "Stage 48" in doc
    assert "Stage 241" in doc
