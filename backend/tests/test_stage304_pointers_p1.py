"""Stage 304 P1 — commercial billing deferred pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-billing-deferred-pack-rg-pointers.json"


def test_commercial_billing_deferred_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 304 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["billing_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "commercial_billing_deferred_stage76",
        "billing_deferred_honesty_pack_remaining_gate_stage303",
        "billing_deferred_pack_remaining_gate",
        "billing_deferred_honesty_stage36",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "cbdprp-billing-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_commercial_billing_deferred_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/COMMERCIAL_BILLING_DEFERRED_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "COMMERCIAL_BILLING_DEFERRED_MVP.md" in doc
    assert "BILLING_DEFERRED_HONESTY_PACK_REMAINING_GATE_MVP.md" in doc
    assert "BILLING_DEFERRED_PACK_REMAINING_GATE_MVP.md" in doc
    assert "BILLING_DEFERRED_HONESTY_MVP.md" in doc
    assert "billing_complete_claimed" in doc
    assert "payment_provider_claimed" in doc
