"""Stage 272 I1 — Subscription renewal pack remaining-gate index hub packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "subscription-renewal-pack-remaining-gate.json"


def test_subscription_renewal_pack_remaining_gate_register_i1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 272 and data["pack"] == "I1"
    assert data["packaging_complete"] is True
    assert data["billing_complete_claimed"] is False
    assert data["subscriptions_live_claimed"] is False
    assert data["annual_discount_enforcement_claimed"] is False
    assert data["go_live_claimed"] is False
    assert data["distinct_from_stage52_r1_subscription_renewal"] is True
    assert data["distinct_from_stage271_billing_deferred_pack_remaining_gate"] is True
    assert data["distinct_from_stage36_b1_billing_deferred_honesty"] is True
    assert data["distinct_from_stage270_shared_schema_tenancy_pack_remaining_gate"] is True
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "srpr-subscriptions-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_subscription_renewal_pack_remaining_gate_doc_i1():
    doc = (ROOT / "docs/SUBSCRIPTION_RENEWAL_PACK_REMAINING_GATE_MVP.md").read_text(encoding="utf-8")
    assert "billing_complete_claimed" in doc
    assert "subscriptions_live_claimed" in doc
    assert "SUBSCRIPTION_RENEWAL_PACK_RG_BLOCKERS_MVP.md" in doc
    assert "SUBSCRIPTION_RENEWAL_PACK_RG_POINTERS_MVP.md" in doc
    assert "Stage 52" in doc
    assert "Stage 36" in doc or "ADR-002" in doc or "ADR_002" in doc
