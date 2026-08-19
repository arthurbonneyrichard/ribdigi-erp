"""Stage 324 B1 — customer assurance pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "customer-assurance-pack-rg-blockers.json"


def test_customer_assurance_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 324 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["customer_assurance_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["customer_assurance_claimed"] == "REMAINING"
    assert blockers["assurance_claimed"] == "REMAINING"
    assert blockers["evidence_chain_live_claimed"] == "REMAINING"
    assert blockers["residual_risks_closed_claimed"] == "REMAINING"
    assert blockers["stage195_as_live_customer_assurance"] == "NON_CLAIM"
    assert blockers["customer_assurance_claimed_flag"] == "false"
    assert blockers["evidence_chain_live_claimed_flag"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "casprb-assurance-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_customer_assurance_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/CUSTOMER_ASSURANCE_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "customer_assurance_claimed" in doc
    assert "evidence_chain_live_claimed" in doc
    assert "Stage 195" in doc
