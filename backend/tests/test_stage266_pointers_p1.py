"""Stage 266 P1 — Ribdigi House console pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "ribdigi-house-console-pack-rg-pointers.json"


def test_ribdigi_house_console_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 266 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["billing_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "ribdigi_house_console_stage68_h1",
        "post_launch_continuity_pack_remaining_gate_stage265",
        "production_hypercare_pack_remaining_gate_stage264",
        "billing_deferred_honesty_stage36",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "rhcprp-billing-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_ribdigi_house_console_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/RIBDIGI_HOUSE_CONSOLE_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "RIBDIGI_HOUSE_CONSOLE_MVP.md" in doc
    assert "POST_LAUNCH_CONTINUITY_PACK_REMAINING_GATE_MVP.md" in doc
    assert "PRODUCTION_HYPERCARE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "BILLING_DEFERRED_HONESTY_MVP.md" in doc
    assert "billing_complete_claimed" in doc
    assert "subscriptions_live_claimed" in doc
