"""Stage 339 I1 — cashier quickstart pack remaining-gate index hub packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "cashier-quickstart-pack-remaining-gate.json"


def test_cashier_quickstart_pack_remaining_gate_register_i1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 339 and data["pack"] == "I1"
    assert data["packaging_complete"] is True
    assert data["offline_complete_claimed"] is False
    assert data["live_training_claimed"] is False
    assert data["go_live_claimed"] is False
    assert data["attestation_claimed"] is False
    assert data["fabricated_cashier_cert_claimed"] is False
    assert data["distinct_from_stage172_cashier_quickstart"] is True
    assert data["distinct_from_stage338_troubleshooting_index_pack_remaining_gate"] is True
    assert data["distinct_from_stage337_faq_offline_pos_pack_remaining_gate"] is True
    assert data["distinct_from_stage329_offline_complete_pack_remaining_gate"] is True
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "cqpr-quickstart-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_cashier_quickstart_pack_remaining_gate_doc_i1():
    doc = (ROOT / "docs/CASHIER_QUICKSTART_PACK_REMAINING_GATE_MVP.md").read_text(encoding="utf-8")
    assert "offline_complete_claimed" in doc
    assert "live_training_claimed" in doc
    assert "CASHIER_QUICKSTART_PACK_RG_BLOCKERS_MVP.md" in doc
    assert "CASHIER_QUICKSTART_PACK_RG_POINTERS_MVP.md" in doc
    assert "Stage 172" in doc
    assert "CASHIER_QUICKSTART_MVP.md" in doc
    assert "OFFLINE_COMPLETE_PACK_REMAINING_GATE_MVP.md" in doc
