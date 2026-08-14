"""Stage 242 B1 — customer training cert pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "customer-training-cert-pack-rg-blockers.json"


def test_customer_training_cert_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 242 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_training_claimed"] is False
    assert data["training_complete_claimed"] is False
    assert data["training_certification_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_training_delivery_execution"] == "REMAINING"
    assert blockers["training_certification_complete"] == "REMAINING"
    assert blockers["stage48_t1_as_live_training"] == "NON_CLAIM"
    assert blockers["stage48_t1_as_training_certification"] == "NON_CLAIM"
    assert blockers["stage241_i1_as_live_training"] == "NON_CLAIM"
    assert blockers["live_training_claimed"] == "false"
    assert blockers["training_certification_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ctcprb-training-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_customer_training_cert_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/CUSTOMER_TRAINING_CERT_PACK_RG_BLOCKERS_MVP.md").read_text(
        encoding="utf-8"
    )
    assert "live_training_claimed" in doc
    assert "training_certification_claimed" in doc
    assert "Stage 48" in doc
