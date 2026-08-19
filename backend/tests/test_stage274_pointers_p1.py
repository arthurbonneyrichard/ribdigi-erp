"""Stage 274 P1 — Language i18n pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "language-i18n-pack-rg-pointers.json"


def test_language_i18n_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 274 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["multilang_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "language_i18n_adr006",
        "store_membership_pack_remaining_gate_stage273",
        "subscription_renewal_pack_remaining_gate_stage272",
        "i18n_remaining_gate_stage184",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "liprp-multilang-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_language_i18n_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/LANGUAGE_I18N_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "ADR_006_LANGUAGE_I18N.md" in doc
    assert "STORE_MEMBERSHIP_PACK_REMAINING_GATE_MVP.md" in doc
    assert "SUBSCRIPTION_RENEWAL_PACK_REMAINING_GATE_MVP.md" in doc
    assert "I18N_REMAINING_GATE_MVP.md" in doc
    assert "multilang_complete_claimed" in doc
    assert "non_english_packs_claimed" in doc
