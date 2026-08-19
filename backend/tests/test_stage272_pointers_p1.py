"""Stage 272 P1 — Subscription renewal pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "subscription-renewal-pack-rg-pointers.json"


def test_subscription_renewal_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 272 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["billing_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "subscription_renewal_stage52_r1",
        "billing_deferred_pack_remaining_gate_stage271",
        "billing_deferred_honesty_stage36",
        "billing_deferred_adr002",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "srprp-subscriptions-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_subscription_renewal_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/SUBSCRIPTION_RENEWAL_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "SUBSCRIPTION_RENEWAL_MVP.md" in doc
    assert "BILLING_DEFERRED_PACK_REMAINING_GATE_MVP.md" in doc
    assert "BILLING_DEFERRED_HONESTY_MVP.md" in doc
    assert "ADR_002_BILLING_DEFERRED.md" in doc
    assert "billing_complete_claimed" in doc
    assert "subscriptions_live_claimed" in doc
