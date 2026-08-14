"""Stage 272 B1 — Subscription renewal pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "subscription-renewal-pack-rg-blockers.json"


def test_subscription_renewal_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 272 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["billing_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["billing_complete"] == "REMAINING"
    assert blockers["subscriptions_live_complete"] == "REMAINING"
    assert blockers["annual_discount_enforcement_complete"] == "REMAINING"
    assert blockers["stage52_r1_as_subscriptions_live"] == "NON_CLAIM"
    assert blockers["billing_complete_claimed"] == "false"
    assert blockers["subscriptions_live_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "srprb-subscriptions-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_subscription_renewal_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/SUBSCRIPTION_RENEWAL_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "billing_complete_claimed" in doc
    assert "subscriptions_live_claimed" in doc
    assert "Stage 52" in doc
