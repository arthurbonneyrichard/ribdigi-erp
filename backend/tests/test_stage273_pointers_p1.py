"""Stage 273 P1 — Store membership pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "store-membership-pack-rg-pointers.json"


def test_store_membership_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 273 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["store_membership_live_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "store_membership_adr005",
        "subscription_renewal_pack_remaining_gate_stage272",
        "billing_deferred_pack_remaining_gate_stage271",
        "membership_remaining_gate_stage182",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "smprp-membership-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_store_membership_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/STORE_MEMBERSHIP_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "ADR_005_USER_STORE_ASSIGNMENT.md" in doc
    assert "SUBSCRIPTION_RENEWAL_PACK_REMAINING_GATE_MVP.md" in doc
    assert "BILLING_DEFERRED_PACK_REMAINING_GATE_MVP.md" in doc
    assert "MEMBERSHIP_REMAINING_GATE_MVP.md" in doc
    assert "store_membership_live_claimed" in doc
    assert "users_store_id_claimed" in doc
